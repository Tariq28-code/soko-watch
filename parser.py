"""
parser.py — turns a raw DSE 'Market Report' text (as returned by
dse.co.tz/get/daily/report/<token>, or copy-pasted from the site/PDF)
into clean structured rows.

Usage:
    from parser import parse_report
    rows, report_date = parse_report(raw_text)
"""

import re
from datetime import datetime

# One counter's price line, e.g.:
# CRDB 710 720 730 710 1,042,638,710 303 1,483,268 1,880.52 614,913 273,618
ROW_RE = re.compile(
    r"^([A-Z]{2,10})(\*\*)?\s+"          # symbol, optional ** (suspended)
    r"([\d,]+)\s+"                        # open
    r"([\d,]+)\s+"                        # close
    r"([\d,]+)\s+"                        # high
    r"([\d,]+)\s+"                        # low
    r"([\d,]+)\s+"                        # turnover (TZS)
    r"(\d+)\s+"                           # deals
    r"([\d,]+)\s+"                        # volume (shares)
    r"([\d,.]+)\s+"                       # market cap (bln TZS)
    r"([\d,]+)\s+"                        # outstanding bids
    r"([\d,]+)\s*$"                       # outstanding offers
)

DATE_RE = re.compile(r"DATE:\s*(\d{1,2}[-\s][A-Za-z]+[-\s]\d{4})")

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5,
    "june": 6, "july": 7, "august": 8, "september": 9, "october": 10,
    "november": 11, "december": 12,
}


def _to_num(s):
    return float(s.replace(",", ""))


def _parse_date(date_str):
    # formats seen: "18-February-2025" or "18 February 2025"
    date_str = date_str.replace("-", " ")
    parts = date_str.split()
    day, month_name, year = int(parts[0]), parts[1].lower(), int(parts[2])
    month = MONTHS.get(month_name)
    if not month:
        return None
    return datetime(year, month, day).date()


def parse_report(raw_text: str):
    """
    Returns (rows, report_date)
    rows: list of dicts, one per counter, with keys:
        symbol, suspended, open, close, high, low, turnover_tzs,
        deals, volume, market_cap_bln_tzs, bids, offers
    report_date: datetime.date or None if not found
    """
    date_match = DATE_RE.search(raw_text)
    report_date = _parse_date(date_match.group(1)) if date_match else None

    rows = []
    seen_symbols = set()
    for line in raw_text.splitlines():
        line = line.strip()
        if not line or line.lower().startswith("total"):
            continue
        m = ROW_RE.match(line)
        if not m:
            continue
        symbol = m.group(1)
        if symbol in seen_symbols:
            continue  # report repeats the header table on page 2; skip dupes
        seen_symbols.add(symbol)
        rows.append({
            "symbol": symbol,
            "suspended": bool(m.group(2)),
            "open": _to_num(m.group(3)),
            "close": _to_num(m.group(4)),
            "high": _to_num(m.group(5)),
            "low": _to_num(m.group(6)),
            "turnover_tzs": _to_num(m.group(7)),
            "deals": int(m.group(8)),
            "volume": _to_num(m.group(9)),
            "market_cap_bln_tzs": _to_num(m.group(10)),
            "bids": _to_num(m.group(11)),
            "offers": _to_num(m.group(12)),
        })
    return rows, report_date


if __name__ == "__main__":
    with open("sample_report.txt") as f:
        text = f.read()
    rows, report_date = parse_report(text)
    print(f"Report date: {report_date}")
    print(f"Parsed {len(rows)} counters\n")
    for r in rows[:5]:
        print(r)
