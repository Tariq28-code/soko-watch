# Getting daily report text in — without bot-hammering dse.co.tz

dse.co.tz's robots.txt disallows automated crawlers on the report
archive pages. Their market-data page also offers to waive historical
data fees for **academic/educational use** — worth applying for as a
MUST student; that's the cleanest long-term source.

Until that's sorted, here's a workflow that keeps a human in the loop
(so it isn't "bot scraping") but still takes you under a minute a day:

## Option A — copy/paste (simplest, works today)
1. Each evening, open DSE's market report page in your browser.
2. Copy the report text for the day.
3. Paste it into a new file, e.g. `reports/2026-08-08.txt`.
4. Run: `python3 ingest.py reports/2026-08-08.txt`

## Option B — a personal, rate-limited fetch script
If you want to automate step 1–2 on **your own machine** (not a
server hammering the site repeatedly), write a tiny script that:
- runs once a day, after market close (after 4:00 PM EAT)
- fetches a single report page
- saves the text to `reports/YYYY-MM-DD.txt`

That's one request a day — nothing close to what robots.txt is meant
to stop. I didn't wire this into the sandbox because I can't verify
today's report token/URL from here reliably (it's a per-report
encrypted token, not a predictable date-based URL) — you'd want to
find today's "Download Daily Report" link on the market-report page
in your own browser and pass it to the script. Ask me and I'll write
that script the moment you're ready — it plugs straight into
`ingest.py`, nothing else changes.

## Once the CMSA/educational waiver comes through
Swap in a proper authenticated feed. `parser.py`, `database.py`,
`analysis.py`, and `dashboard.html` don't need to change at all —
they only care about getting raw report text or structured rows.
