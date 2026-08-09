"""
analysis.py — turns raw price history for one counter into the
"top facts" and a buy/hold/sell call.

DSE-specific reality this is built around:
- Only ~28 counters, many trade a handful of days a month. So we can't
  lean on classic daily-bar technicals (RSI-14 etc.) the way a US-stock
  tool would — half the "days" have zero trades.
- Signals here are deliberately simple and explainable, not a black box:
  trend, momentum, liquidity, and order-book pressure. Each signal is
  returned with its own reasoning string so the dashboard can show WHY,
  not just a color.
- This is decision support, not financial advice — the output always
  says so, and always shows its work.
"""

from datetime import datetime

MIN_POINTS_FOR_TREND = 5


def _traded_closes(history):
    """Only keep days where the counter actually traded (volume > 0),
    since untraded days repeat the last close and would flatten trend
    signals artificially."""
    return [h for h in history if h["volume"] and h["volume"] > 0]


def _sma(values, n):
    if len(values) < n:
        return None
    return sum(values[-n:]) / n


def _fundamentals_facts(fundamentals):
    """
    fundamentals: dict from database.get_latest_fundamentals(symbol), or None.
    Returns (facts_list, score_adjustment). Only comments on ratios where
    both inputs needed are actually present — never guesses at a missing
    figure.
    """
    if not fundamentals:
        return (["No fundamentals on file yet for this company — add them "
                  "via load_fundamentals.py from its latest annual report."], 0)

    facts = []
    score = 0
    period = fundamentals.get("period_end", "unknown period")
    revenue = fundamentals.get("revenue_mln_tzs")
    net_income = fundamentals.get("net_income_mln_tzs")
    debt = fundamentals.get("total_debt_mln_tzs")
    equity = fundamentals.get("total_equity_mln_tzs")
    assets = fundamentals.get("total_assets_mln_tzs")

    # Profitability
    if revenue and net_income is not None:
        margin = net_income / revenue * 100
        if margin < 0:
            facts.append(f"Reported a net loss for {period} (net margin {margin:.1f}%).")
            score -= 1
        elif margin < 5:
            facts.append(f"Thin net margin for {period} ({margin:.1f}%) — profitable, but not by much.")
        else:
            facts.append(f"Net margin of {margin:.1f}% for {period}.")
            score += 0.5

    # Leverage — debt relative to equity
    if debt is not None and equity:
        d_to_e = debt / equity
        if d_to_e > 2:
            facts.append(f"Highly leveraged — debt is {d_to_e:.1f}x equity as of {period}. Debt-funded growth carries more downside if earnings soften.")
            score -= 1
        elif d_to_e > 1:
            facts.append(f"Moderately leveraged — debt is {d_to_e:.1f}x equity as of {period}.")
        elif d_to_e >= 0:
            facts.append(f"Low leverage — debt is only {d_to_e:.1f}x equity as of {period}.")
            score += 0.5

    # Debt relative to total assets (how much of the balance sheet is borrowed)
    if debt is not None and assets:
        debt_ratio = debt / assets * 100
        facts.append(f"Debt makes up {debt_ratio:.0f}% of total assets as of {period}.")

    if fundamentals.get("dividend_per_share_tzs"):
        facts.append(f"Last declared dividend: TZS {fundamentals['dividend_per_share_tzs']:,.0f} per share.")

    if not facts:
        facts.append(f"Fundamentals on file for {period}, but key figures (revenue, net income, debt, or equity) are still blank — fill in load_fundamentals.py's CSV to unlock this.")

    return facts, score


def compute_signals(symbol, history, fundamentals=None):
    """
    history: list of row-dicts for one symbol, ORDERED BY DATE ASC
             (as returned by database.get_history)
    fundamentals: optional dict from database.get_latest_fundamentals(symbol)
                  — income/debt facts are folded in when present.
    Returns a dict of facts + a recommendation.
    """
    if not history:
        return {"symbol": symbol, "call": "NO DATA", "facts": [], "confidence": "none"}

    latest = history[-1]
    traded = _traded_closes(history)
    closes = [h["close"] for h in traded]

    facts = []
    score = 0  # rough -2..+2 signal accumulator, kept simple & explainable

    # --- 1. Suspension check (overrides everything) ---
    if latest["suspended"]:
        return {
            "symbol": symbol,
            "call": "SUSPENDED",
            "confidence": "n/a",
            "last_close": latest["close"],
            "facts": ["Trading in this counter is currently suspended."],
        }

    # --- 2. Trend: short vs long moving average, on TRADED days only ---
    sma_short = _sma(closes, 3)
    sma_long = _sma(closes, min(10, len(closes))) if len(closes) >= MIN_POINTS_FOR_TREND else None
    if sma_short and sma_long:
        if sma_short > sma_long * 1.01:
            score += 1
            facts.append(f"Short-term price trend is rising ({sma_short:,.0f} vs {sma_long:,.0f} longer average).")
        elif sma_short < sma_long * 0.99:
            score -= 1
            facts.append(f"Short-term price trend is falling ({sma_short:,.0f} vs {sma_long:,.0f} longer average).")
        else:
            facts.append("Price has been flat relative to its recent average.")
    else:
        facts.append("Not enough trading history yet for a reliable trend read.")

    # --- 3. Momentum: latest traded close vs close ~N trades ago ---
    if len(closes) >= 2:
        lookback = closes[-min(5, len(closes))]
        latest_close = closes[-1]
        pct = (latest_close - lookback) / lookback * 100 if lookback else 0
        if pct > 3:
            score += 1
            facts.append(f"Up {pct:.1f}% over its last {min(5, len(closes))} traded sessions.")
        elif pct < -3:
            score -= 1
            facts.append(f"Down {abs(pct):.1f}% over its last {min(5, len(closes))} traded sessions.")
        else:
            facts.append(f"Roughly flat ({pct:+.1f}%) over its last {min(5, len(closes))} traded sessions.")

    # --- 4. Liquidity: how often/how much it actually trades ---
    recent = history[-10:]
    trade_days = sum(1 for h in recent if h["volume"] and h["volume"] > 0)
    liquidity_ratio = trade_days / len(recent)
    if liquidity_ratio < 0.3:
        facts.append(f"Thinly traded — only active on {trade_days}/{len(recent)} of the last recorded sessions. Treat any signal here with caution; you may struggle to buy or sell at a fair price quickly.")
        score -= 0.5
    else:
        facts.append(f"Reasonably liquid — traded on {trade_days}/{len(recent)} of the last recorded sessions.")

    # --- 5. Order-book pressure: outstanding bids vs offers ---
    bids, offers = latest.get("bids") or 0, latest.get("offers") or 0
    if bids + offers > 0:
        bid_share = bids / (bids + offers)
        if bid_share > 0.65:
            score += 0.5
            facts.append(f"Order book is buyer-heavy — {bid_share*100:.0f}% of outstanding orders are bids (demand outweighs supply).")
        elif bid_share < 0.35:
            score -= 0.5
            facts.append(f"Order book is seller-heavy — {(1-bid_share)*100:.0f}% of outstanding orders are offers (supply outweighs demand).")

    # --- 6. Fundamentals: income & debt, when we have them on file ---
    fund_facts, fund_score = _fundamentals_facts(fundamentals)
    facts.extend(fund_facts)
    score += fund_score

    # --- Final call ---
    n_points = len(traded)
    if n_points < MIN_POINTS_FOR_TREND:
        call = "WATCH"
        confidence = "low (limited history)"
    elif score >= 1.5:
        call = "BUY"
        confidence = "moderate"
    elif score <= -1.5:
        call = "SELL"
        confidence = "moderate"
    else:
        call = "HOLD"
        confidence = "moderate"

    return {
        "symbol": symbol,
        "call": call,
        "confidence": confidence,
        "score": round(score, 2),
        "last_close": latest["close"],
        "last_date": latest["date"],
        "facts": facts,
    }


def analyze_all(symbols, history_fn, fundamentals_fn=None):
    """
    symbols: list of symbol strings.
    history_fn(symbol) -> ordered history list.
    fundamentals_fn(symbol) -> latest fundamentals dict or None (optional).
    """
    if fundamentals_fn:
        return [compute_signals(s, history_fn(s), fundamentals_fn(s)) for s in symbols]
    return [compute_signals(s, history_fn(s)) for s in symbols]
