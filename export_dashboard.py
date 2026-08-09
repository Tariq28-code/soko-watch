"""
export_dashboard.py — runs analysis for every symbol in the DB and
writes dashboard_data.json for the frontend to consume.
"""

import json
from database import get_all_symbols, get_history, get_latest_date, get_latest_fundamentals
from analysis import analyze_all


def export(db_path="dse.db", out_path="dashboard_data.json"):
    symbols = get_all_symbols(db_path)
    results = analyze_all(
        symbols,
        lambda s: get_history(s, db_path),
        lambda s: get_latest_fundamentals(s, db_path),
    )
    # Raw inputs are shipped too so the frontend can re-run the same
    # analysis in-browser when you paste/import a report that isn't in
    # the database yet. `counters` stays the pre-computed server view;
    # `history` + `fundamentals` let the page blend new reports into it.
    payload = {
        "generated_from_latest_report": get_latest_date(db_path),
        "counters": results,
        "history": {s: get_history(s, db_path) for s in symbols},
        "fundamentals": {s: get_latest_fundamentals(s, db_path) for s in symbols},
    }
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote {len(results)} counters to {out_path}")
    return payload


if __name__ == "__main__":
    export()
