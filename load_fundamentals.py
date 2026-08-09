"""
load_fundamentals.py — reads a CSV of company fundamentals (revenue,
net income, debt, equity, etc.) and loads it into the database.

Where to get the numbers: each company's audited annual report, found
either on dse.co.tz's company/announcements pages or the company's own
investor-relations page. Look for the Statement of Comprehensive
Income (revenue, net income) and Statement of Financial Position
(debt, equity, total assets).

Usage:
    python3 load_fundamentals.py fundamentals_template.csv
    (copy the template, fill in numbers you've found, then load it —
    re-running is safe, it overwrites by (symbol, period_end))
"""

import csv
import sys
from database import init_db, upsert_fundamentals


def _num(s):
    s = (s or "").strip()
    return float(s) if s else None


def load_csv(path, db_path="dse.db"):
    init_db(db_path)
    n_loaded, n_skipped = 0, 0
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get("revenue_mln_tzs") and not row.get("net_income_mln_tzs") \
               and not row.get("total_debt_mln_tzs"):
                n_skipped += 1
                continue  # blank template row — nothing filled in yet
            record = {
                "symbol": row["symbol"].strip().upper(),
                "period_end": row["period_end"].strip(),
                "period_type": row["period_type"].strip(),
                "revenue_mln_tzs": _num(row.get("revenue_mln_tzs")),
                "net_income_mln_tzs": _num(row.get("net_income_mln_tzs")),
                "total_debt_mln_tzs": _num(row.get("total_debt_mln_tzs")),
                "total_equity_mln_tzs": _num(row.get("total_equity_mln_tzs")),
                "total_assets_mln_tzs": _num(row.get("total_assets_mln_tzs")),
                "dividend_per_share_tzs": _num(row.get("dividend_per_share_tzs")),
                "source": row.get("source", "").strip(),
            }
            upsert_fundamentals(record, db_path)
            n_loaded += 1
    print(f"Loaded {n_loaded} fundamentals rows, skipped {n_skipped} blank rows.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 load_fundamentals.py <path_to_fundamentals.csv>")
        sys.exit(1)
    load_csv(sys.argv[1])
