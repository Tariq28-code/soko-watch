"""
database.py — SQLite storage for DSE daily price history.
One row per (symbol, date). Re-running ingest for the same date
overwrites cleanly (safe to re-import a day you already have).
"""

import sqlite3
from contextlib import contextmanager

DB_PATH = "dse.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS prices (
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,          -- ISO format YYYY-MM-DD
    suspended INTEGER NOT NULL,
    open REAL, close REAL, high REAL, low REAL,
    turnover_tzs REAL,
    deals INTEGER,
    volume REAL,
    market_cap_bln_tzs REAL,
    bids REAL,
    offers REAL,
    PRIMARY KEY (symbol, date)
);
CREATE INDEX IF NOT EXISTS idx_prices_symbol ON prices(symbol);
CREATE INDEX IF NOT EXISTS idx_prices_date ON prices(date);

-- Fundamentals: one row per company per reporting period (usually
-- annual, sometimes half-year). Filled in by hand from each company's
-- audited financial statements — there's no daily feed for this.
-- All figures in TZS millions unless noted; leave a field blank/NULL
-- if it isn't disclosed for that period.
CREATE TABLE IF NOT EXISTS fundamentals (
    symbol TEXT NOT NULL,
    period_end TEXT NOT NULL,     -- ISO date, e.g. year-end 2025-12-31
    period_type TEXT NOT NULL,    -- 'annual' or 'half-year'
    revenue_mln_tzs REAL,
    net_income_mln_tzs REAL,
    total_debt_mln_tzs REAL,      -- interest-bearing borrowings
    total_equity_mln_tzs REAL,
    total_assets_mln_tzs REAL,
    dividend_per_share_tzs REAL,  -- most recent declared dividend, if any
    source TEXT,                  -- where you got this, e.g. 'FY2025 annual report'
    PRIMARY KEY (symbol, period_end)
);
CREATE INDEX IF NOT EXISTS idx_fund_symbol ON fundamentals(symbol);
"""


@contextmanager
def get_conn(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path=DB_PATH):
    with get_conn(db_path) as conn:
        conn.executescript(SCHEMA)


def insert_rows(rows, report_date, db_path=DB_PATH):
    """rows: output of parser.parse_report(). report_date: datetime.date"""
    if report_date is None:
        raise ValueError("report_date is required — could not parse a date from the report")
    date_str = report_date.isoformat()
    with get_conn(db_path) as conn:
        for r in rows:
            conn.execute(
                """INSERT OR REPLACE INTO prices
                   (symbol, date, suspended, open, close, high, low,
                    turnover_tzs, deals, volume, market_cap_bln_tzs, bids, offers)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (r["symbol"], date_str, int(r["suspended"]), r["open"], r["close"],
                 r["high"], r["low"], r["turnover_tzs"], r["deals"], r["volume"],
                 r["market_cap_bln_tzs"], r["bids"], r["offers"]),
            )
    return len(rows)


def get_history(symbol, db_path=DB_PATH):
    with get_conn(db_path) as conn:
        cur = conn.execute(
            "SELECT * FROM prices WHERE symbol=? ORDER BY date ASC", (symbol,)
        )
        return [dict(row) for row in cur.fetchall()]


def get_all_symbols(db_path=DB_PATH):
    with get_conn(db_path) as conn:
        cur = conn.execute("SELECT DISTINCT symbol FROM prices ORDER BY symbol")
        return [row["symbol"] for row in cur.fetchall()]


def get_latest_date(db_path=DB_PATH):
    with get_conn(db_path) as conn:
        cur = conn.execute("SELECT MAX(date) as d FROM prices")
        row = cur.fetchone()
        return row["d"] if row else None


def upsert_fundamentals(record, db_path=DB_PATH):
    """
    record: dict with keys matching the fundamentals table
            (symbol, period_end, period_type required; rest optional)
    """
    required = ("symbol", "period_end", "period_type")
    for k in required:
        if not record.get(k):
            raise ValueError(f"fundamentals record missing required field: {k}")
    cols = ["symbol", "period_end", "period_type", "revenue_mln_tzs",
            "net_income_mln_tzs", "total_debt_mln_tzs", "total_equity_mln_tzs",
            "total_assets_mln_tzs", "dividend_per_share_tzs", "source"]
    values = [record.get(c) for c in cols]
    placeholders = ",".join("?" * len(cols))
    with get_conn(db_path) as conn:
        conn.execute(
            f"INSERT OR REPLACE INTO fundamentals ({','.join(cols)}) VALUES ({placeholders})",
            values,
        )


def get_fundamentals(symbol, db_path=DB_PATH):
    """Returns fundamentals rows for a symbol, most recent period first."""
    with get_conn(db_path) as conn:
        cur = conn.execute(
            "SELECT * FROM fundamentals WHERE symbol=? ORDER BY period_end DESC",
            (symbol,),
        )
        return [dict(row) for row in cur.fetchall()]


def get_latest_fundamentals(symbol, db_path=DB_PATH):
    rows = get_fundamentals(symbol, db_path)
    return rows[0] if rows else None
