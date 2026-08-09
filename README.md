# Soko Watch — DSE Tracker

A pipeline that turns Dar es Salaam Stock Exchange daily reports into
a dashboard with per-counter BUY / HOLD / WATCH / SELL calls — with
the reasoning always shown.

## How it fits together

```
raw report text  →  parser.py   →  structured rows
                     ↓
                database.py     →  dse.db (SQLite, grows every day you ingest)
                     ↓
                analysis.py     →  trend / momentum / liquidity / order-book signals
                     ↓
             export_dashboard.py → dashboard_data.json
                     ↓
               dashboard.html   →  the board you actually look at
```

Each piece only talks to the one next to it, so any piece can be
swapped later (e.g. a real-time feed instead of daily reports, or a
Flask backend instead of a static JSON file) without touching the rest.

## Running it yourself

```bash
# 1. Get today's report text (see fetch_note.md)
#    save it as e.g. reports/2026-08-08.txt

# 2. Ingest it
python3 ingest.py reports/2026-08-08.txt

# 3. Re-run analysis + export
python3 export_dashboard.py

# 4. Open dashboard.html in a browser
#    (it reads dashboard_data.json when served from a web server,
#    and falls back to its embedded snapshot on a bare file:// path)
```

Do this daily (even just a couple of minutes after market close) and
within 2–3 weeks the trend/momentum signals stop saying "not enough
history" and start meaning something.

## Why so many counters say WATCH right now

The demo dashboard is seeded with **one real day** of DSE data
(18 Feb 2025) to prove the whole pipeline end-to-end. With one data
point there's no trend to read — so almost everything correctly
comes back WATCH. That's the analysis engine being honest, not
broken. Keep ingesting daily reports and the picture sharpens.

## Wiring dashboard.html to live data

`dashboard.html` tries `fetch('dashboard_data.json')` first, and only
falls back to its embedded snapshot if that fails (e.g. when opened
off a bare `file://` path). So it works two ways with no edits:

- **Served from a web server** (GitHub Pages, `python3 -m http.server 8000`, …)
  → reads the freshly exported `dashboard_data.json`.
- **Opened directly as a file** → shows the embedded snapshot.

Re-run `export_dashboard.py` after each day's ingest to refresh the
JSON the server serves.

### Importing a report right in the browser

The board has a **"+ Import report"** button: paste the day's report
text (or choose the `.txt` file) and it parses and re-analyzes the
whole board in your browser, blending the new day into the history
shipped in `dashboard_data.json`. Imports are saved to the browser's
`localStorage`, so they persist across refreshes on that device.

This is a quick local preview only — nothing leaves the page, and the
public site won't change. To publish an imported report for everyone,
still save the text to `reports/YYYY-MM-DD.txt` and push; the
server-side pipeline then produces the authoritative data.

## Deployment (GitHub Pages — set up)

The repo ships with `.github/workflows/deploy.yml`. It rebuilds the
whole data pipeline and deploys the static site to GitHub Pages:

- **On every push to `main`** — after you commit a new report or
  fundamentals row, the site updates immediately.
- **On a schedule** (Mon–Fri 17:30 EAT, after market close) — a
  safety net if you push a report late.
- **Manually** — "Run workflow" in the Actions tab.

Because every daily report is committed as plain text under
`reports/`, the build is fully reproducible and never touches
dse.co.tz (no requests at all — the human copy-paste step in
`fetch_note.md` remains the only way data enters).

**To deploy, one-time setup:**

1. Create a repo on GitHub (e.g. `soko-watch`) and push this folder:
   ```bash
   git init
   git add .
   git commit -m "Soko Watch — DSE tracker"
   git branch -M main
   git remote add origin https://github.com/<you>/soko-watch.git
   git push -u origin main
   ```
2. In the repo, go to **Settings → Pages** and set **Source** to
   **"GitHub Actions"** (not "Deploy from a branch"). First run may
   need a manual "Run workflow" to appear.
3. Your board is live at `https://<you>.github.io/soko-watch/`.

**Daily habit:** paste the day's report into
`reports/2026-08-08.txt`, `git add` + commit + push. The Action
ingests it, refreshes the analysis, and re-deploys.

- **If you want a live backend later:** PythonAnywhere or Render free
  tier can run the Python scripts on a daily cron instead — the
  pipeline scripts don't change at all.

## Extending the analysis ("top facts")

The pipeline now covers two data sources:

1. **Daily price reports** → trend, momentum, liquidity, order-book pressure (automatic, from `ingest.py`).
2. **Company fundamentals** → profitability (net margin), leverage (debt-to-equity, debt-to-assets), and dividend history (manual, from `load_fundamentals.py`).

### Adding income/debt data for a company

There's no daily feed for this — it only exists in each company's
audited financial statements (annual reports, or quarterly/half-year
interim reports), published on `dse.co.tz`'s announcements page or
the company's own investor-relations page.

1. Open `fundamentals_template.csv`, add a row per company per
   reporting period. Leave any field blank if you can't find it —
   the analysis only comments on ratios where it has real numbers,
   it never guesses.
2. Run: `python3 load_fundamentals.py fundamentals_template.csv`
3. Run `python3 export_dashboard.py` again to fold it into the dashboard.

**One important nuance for banks** (CRDB, NMB, DCB, MKCB, MCB,
MUCOBA): their core liability is customer deposits, not the kind of
interest-bearing debt an industrial company takes on. A high
"debt-to-equity" number for a bank doesn't mean the same thing it
would for, say, TBL or TPCC. For banks, leave `total_debt_mln_tzs`
blank and instead look at metrics banks actually get judged on —
capital adequacy ratio, non-performing loan ratio, return on
equity — which aren't in this schema yet but would be a good next
addition specifically for the banking counters (CRDB, NMB, DCB,
MKCB, MCB, MUCOBA, NICO).

The CSV currently has two real, sourced rows for CRDB (Q3 2025
interim, and FY2025 abridged results) to prove the fundamentals
pipeline end-to-end — check CRDB's card in the dashboard, it now
shows the FY2025 dividend fact pulled straight from that data.

### Other extensions worth doing next

- **Sector comparison** — group counters (Banking, Industrial &
  Allied, Commercial Services, etc.) and flag under/over-performance
  vs sector peers, not just vs their own history.
- **Bank-specific ratios** — capital adequacy, NPL ratio, ROE — as
  noted above.

## Files

- `parser.py` — raw report text → structured rows
- `database.py` — SQLite storage (prices + fundamentals)
- `analysis.py` — the actual "top facts" + recommendation logic
- `ingest.py` — CLI: daily report file → database
- `load_fundamentals.py` — CLI: fundamentals CSV → database
- `fundamentals_template.csv` — fill this in from annual/interim reports
- `export_dashboard.py` — database → dashboard_data.json
- `dashboard.html` — the frontend
- `sample_report.txt` — a real DSE report (18 Feb 2025), used to prove the pipeline
- `fetch_note.md` — how to get report text in without bot-hammering dse.co.tz
