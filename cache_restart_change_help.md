# Common Change Tracker — Cache, Refresh, and Stability Changes

This document records the dashboard changes made to improve Streamlit Cloud restarts, data freshness visibility, and runtime stability.

## What changed

The dashboard previously displayed:

> Cache missing — run the agent or `python run_once.py` to populate data.

This happened after Streamlit Cloud woke up or recreated its container because `cache.json` is generated at runtime and is not guaranteed to survive a Cloud restart. The local computer did not show the problem because its local filesystem kept the generated file.

The application now starts safely even when the runtime cache is missing.

## How the new startup flow works

1. The app first looks for the normal runtime file, `cache.json`.
2. If that file is missing, the app restores the tracked startup snapshot from `data/cache_seed.json`.
3. The dashboard displays the snapshot instead of stopping with a cache-missing warning.
4. Use **Run Setup Script** in the sidebar when fresh market data is needed.
5. The setup script writes a new runtime `cache.json` and the dashboard loads it after rerunning.

The snapshot is only a startup fallback. It is not intended to replace the normal market-data refresh process.

## Files changed

- `app.py` — detects a missing runtime cache and restores the fallback snapshot.
- `app.py` — displays a freshness alert when data is more than 60 minutes old during regular market hours.
- `app.py` — reloads at 8:30 AM, hourly from 9:30 AM through 4:30 PM, and at 5:00 PM Eastern on weekdays.
- `app.py` — includes a compatibility fallback so older Cloud revisions can start even if `cache_utils.py` is missing or incomplete.
- `app.py` — safely converts missing projection prices to numeric values before rounding, preventing the pandas `TypeError` shown in the dashboard.
- `app.py` — protects projection charts from all-missing or object-typed price columns.
- `cache_utils.py` — contains reusable cache recovery, cache-age formatting, and market-hours helpers.
- `data/cache_seed.json` — tracked fallback data used after a Cloud restart.
- `agent.py` — writes the cache atomically through a temporary file before replacing the old cache. This prevents the dashboard from reading a partially written JSON file.
- `.gitignore` — continues to ignore generated `cache.json` and now also ignores `cache.json.tmp`.
- `test_cache_recovery.py` — verifies cache recovery, cache-age formatting, market-hours logic, and missing projection values.
- `README.md` — documents the Streamlit Cloud deployment, refresh, and freshness behavior.
- `cache_restart_change_help.md` — displayed at the bottom of the app under **Common Change Tracker** and available from the sidebar.
- `data/snapshots/` — stores timestamped dashboard PDF snapshots created from the app.
- `requirements.txt` — includes `reportlab` for dashboard PDF generation.
- `.streamlit/secrets.toml.example` — template for configuring permanent GitHub snapshot storage.

## Change history

### Cache restart resilience

- Added `data/cache_seed.json` as a tracked startup snapshot.
- Restored the snapshot automatically when Streamlit Cloud loses runtime `cache.json` storage.
- Kept generated runtime files out of Git while ensuring the deployed app has usable fallback data.

### Data freshness and scheduled refresh

- Added a market-aware alert for cache data older than 60 minutes during regular US trading hours.
- Added readable cache-age text such as “11 days, 5 hours, 46 minutes” instead of displaying only a raw minute count.
- Added scheduled weekday browser reloads at 8:30 AM, hourly during the market session, and 5:00 PM Eastern.
- Documented that browser reloads reread the cache but do not download market data; `agent.py` or **Run Setup Script** must update the cache.

### Runtime stability

- Changed cache writes to atomic replacement through `cache.json.tmp`.
- Fixed the projections panel crash when fallback or historical data contains only missing prices.
- Added an import fallback in `app.py` to prevent Cloud startup failure when deployed files are temporarily out of sync.
- Added regression checks for the recovery, freshness, formatting, and projection edge cases.

### Dashboard PDF snapshots

- Added **Take Current Dashboard Snapshot** under **Dashboard Snapshots (PDF)**.
- Each snapshot includes the cache timestamp, Top 10 MTD data, Top-10 Momentum Sleeve rotation candidates, rotation-score explanation, Rotation Scoring Table, Monthly Rotation Summary, historical Top 10 sections, sector performance, and Top 10 S&P 500 breakouts.
- Saved PDFs are listed newest-first with **View / download** links for historical review.
- Each saved snapshot has a **Delete** button that removes the local copy and the permanent GitHub copy when GitHub persistence is configured.
- Snapshots are stored in `data/snapshots/` on the running instance. Local snapshots remain on the local machine; Streamlit Cloud storage may be cleared when the app container is recreated, so long-term Cloud history requires external storage or committing exported PDFs to the repository.
- When `GITHUB_TOKEN`, `GITHUB_REPO`, and `GITHUB_BRANCH` are configured in Streamlit Cloud Secrets, new PDFs are uploaded to the repository through the GitHub Contents API and historical PDFs are restored after Cloud restarts.
- The GitHub token must have fine-grained **Contents: Read and write** permission for the target repository. Never commit the real token to the repository.

## Deployment steps

1. Commit and push all changed files, especially `data/cache_seed.json`, `cache_utils.py`, and `app.py`.
2. Allow Streamlit Cloud to redeploy the repository.
3. Open the app after deployment or after it wakes from sleep.
4. Confirm that the dashboard loads without the old cache-missing warning.
5. Select **Run Setup Script** to refresh the data when required.

## Important notes

- Streamlit Cloud runtime files can be temporary. The fallback file must remain tracked in Git.
- The fallback snapshot can become stale. It is a resilience mechanism, not a live-data source.
- The browser reloads at 8:30 AM, hourly from 9:30 AM through 4:30 PM, and at 5:00 PM Eastern on weekdays. A reload only rereads the cache; it does not download market data by itself.
- Scheduled browser reloads work while the dashboard page is open; browser sleep/background throttling or a sleeping Streamlit Cloud app can delay the reload until the page is active again.
- During regular US market hours, the dashboard warns when the cache is more than 60 minutes old. Use **Run Setup Script** or keep the local `agent.py` updater running to obtain fresh data.
- Cache age is displayed in readable days, hours, and minutes rather than a raw minute total.
- This help is available at the bottom of the dashboard under **Common Change Tracker**.
- Projection tables now tolerate missing values in fallback or older caches without stopping the dashboard.
- The app still requires the normal Python dependencies listed in `requirements.txt`.
- If the setup script fails because a data provider or network request is unavailable, the fallback remains available for viewing the dashboard.

## Verification completed

- Cache recovery behavior was tested for a missing runtime file.
- Existing fresh runtime data was tested to ensure it is preserved.
- The changed Python files passed compilation checks.
