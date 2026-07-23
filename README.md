Top 10 S&P MTD Dashboard

This small project contains:
- `agent.py`: background updater that computes MTD/YTD returns for the S&P 500 and writes `cache.json`.
- `app.py`: Streamlit dashboard that reads `cache.json` and displays the top 10 MTD performers.
- `requirements.txt`: Python dependencies.

Quick start (Windows PowerShell):

1) Create and activate a virtual environment (optional but recommended):

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
```

2) Install requirements:

```powershell
pip install -r requirements.txt
```

3) Start the agent (keeps updating cache every 60s):

```powershell
# Run in an always-open terminal
python agent.py --interval 60

# Or start in background as a job (PowerShell):
Start-Job -ScriptBlock { python "$(Resolve-Path .\agent.py)" --interval 60 }

# To see job list: Get-Job ; To stop: Stop-Job -Id <id>
```

4) (Optional) Set up HTTPS with self-signed certificate:

```powershell
# Generate self-signed certificate for zubeir-ai-server (10-year validity)
python generate_certs.py
```

Then update your hosts file to map the internal IP:
- Open `C:\Windows\System32\drivers\etc\hosts` (as Administrator)
- Add this line: `10.0.0.79 zubeir-ai-server`

To remove the "not secure" warning in your browser:
- Import `certs/zubeir-ai-server.crt` into your browser's trusted certificates
- Or import into Windows Certificate Manager for system-wide trust

5) Run the Streamlit dashboard (separate terminal):

```powershell
# Using the startup script (includes HTTPS if configured):
.\to_run_the_server_and_start_the_frontend.ps1

# Or run Streamlit directly:
streamlit run app.py --server.port 7860 --server.address 0.0.0.0
```

Access the dashboard:
- Local (HTTP): http://localhost:7860
- Local (HTTPS, if certs generated): https://localhost:7860
- Network (HTTP): http://10.0.0.79:7860
- Network (HTTPS, if certs generated): https://zubeir-ai-server:7860

Notes and next steps:
- `agent.py` downloads historic prices for the full S&P 500. That can take some seconds/minutes on first run.
- For production always-on use, create a Windows Scheduled Task or use a process supervisor (nssm) to keep `agent.py` running.
- You can tune `--interval` in seconds to control how often the agent updates.
- The Streamlit app auto-refreshes every 60 seconds; change `AUTO_REFRESH_SECONDS` in `app.py` if you want a different cadence.
- SSL configuration is in `.streamlit/config.toml`; modify as needed for your setup.

Privacy and data:
- Data is fetched from Yahoo Finance via the `yfinance` package.

If you want, I can:
- Add Windows Scheduled Task creation PowerShell commands.
- Turn this into a single Windows service wrapper (using `nssm`) or a Docker deployment.
- Add charts per-ticker or export CSV/alerts/email notifications for big moves.
