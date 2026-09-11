# Cache Restart Change Help

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

- `app.py` — detects a missing runtime cache, restores the fallback, and displays a clear status message.
- `app.py` — displays a freshness alert when data is more than 60 minutes old during regular market hours and reloads at 8:30 AM, hourly during the session, and 5:00 PM Eastern on weekdays.
- `cache_utils.py` — contains the reusable cache-recovery helper.
- `data/cache_seed.json` — tracked fallback data used after a Cloud restart.
- `agent.py` — writes the cache atomically through a temporary file before replacing the old cache. This prevents the dashboard from reading a partially written JSON file.
- `.gitignore` — continues to ignore generated `cache.json` and now also ignores `cache.json.tmp`.
- `test_cache_recovery.py` — verifies fallback recovery and confirms that a fresh runtime cache is never overwritten.
- `README.md` — documents the Streamlit Cloud deployment behavior.

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
- The app still requires the normal Python dependencies listed in `requirements.txt`.
- If the setup script fails because a data provider or network request is unavailable, the fallback remains available for viewing the dashboard.

## Verification completed

- Cache recovery behavior was tested for a missing runtime file.
- Existing fresh runtime data was tested to ensure it is preserved.
- The changed Python files passed compilation checks.
