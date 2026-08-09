"""
ingest.py — feed one day's raw DSE report text into the database.

How you get the raw text (pick one, in order of how automated it is):
  1. [Manual, works today] Open the day's report on dse.co.tz or its
     Facebook/notice PDF, copy the text, save it as a .txt file, run:
         python3 ingest.py path/to/report.txt
  2. [Semi-automated] A small script on YOUR machine (not this sandbox)
     fetches the report page once a day and saves it — see fetch_note.md.
  3. [Fully automated, once you have the educational data waiver] swap
     in a direct HTTP fetch here — everything downstream (parser,
     database, analysis, dashboard) doesn't change at all.
"""

import sys
from parser import parse_report
from database import init_db, insert_rows


def ingest_file(path, db_path="dse.db"):
    with open(path, encoding="utf-8") as f:
        raw_text = f.read()
    rows, report_date = parse_report(raw_text)
    if not rows:
        print("No counters parsed — check the report text / format.")
        return
    if report_date is None:
        print("Warning: could not detect a report date. Skipping insert.")
        return
    init_db(db_path)
    n = insert_rows(rows, report_date, db_path)
    print(f"Ingested {n} counters for {report_date} into {db_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 ingest.py <path_to_report.txt>")
        sys.exit(1)
    ingest_file(sys.argv[1])
