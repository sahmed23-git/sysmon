# SysMon - AI-Powered System Monitor

A Python desktop app that monitors your computer in real time, detects anomalies, generates AI health summaries, and sends Telegram alerts to your phone.

![Python](https://img.shields.io/badge/Python-3.10+-blue) ![Flask](https://img.shields.io/badge/Flask-3.0-green) ![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)

---

## What it does

- **Live monitoring** - tracks CPU, RAM, disk usage, and uptime every 10 seconds
- **Desktop app** - native Windows window with sidebar navigation, no browser needed
- **Web dashboard** - full browser dashboard at `http://localhost:5000`
- **Smart alerts** - detects threshold violations and anomalies (memory leaks, CPU spikes)
- **Telegram notifications** - sends messages to your phone when something goes wrong
- **Recovery alerts** - notifies you when the system returns to normal
- **AI health summaries** - uses Claude API to explain what's wrong in plain English
- **System tray icon** - runs in the background, changes color based on health status

---

## Project Structure

```
sysmon/
├── app.py              # Flask server (backend)
├── agent.py            # Monitoring agent (collects system metrics)
├── desktop_app.py      # Native Windows desktop app
├── database.py         # SQLAlchemy database models
├── alert_engine.py     # Rule-based anomaly detection
├── ai_analyzer.py      # Claude API health summaries
├── telegram_bot.py     # Telegram notification sender
├── launcher.py         # Simple launcher script
├── requirements.txt    # Python dependencies
├── SysMon.bat          # Double-click to launch everything
├── templates/
│   ├── base.html
│   ├── index.html      # Overview dashboard
│   ├── device.html     # Device detail + charts
│   ├── alerts.html     # Alert history
│   └── settings.html   # Configuration
└── static/
    └── css/
        └── main.css
```

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
pip install pystray pillow plyer
```

### 2. Launch the app

**Option A — Double-click** `SysMon.bat` on your Desktop

**Option B — Run manually in two terminals:**

Terminal 1:
```bash
python app.py
```

Terminal 2:
```bash
python agent.py --server http://localhost:5000
```

Then open the desktop app:
```bash
python desktop_app.py
```

### 3. Open the dashboard

- **Desktop app:** run `python desktop_app.py`
- **Browser dashboard:** go to `http://localhost:5000`

---

## Setting Up Telegram Alerts

1. Open Telegram and message **@BotFather**
2. Send `/newbot` and follow the prompts — copy your **bot token**
3. Message **@userinfobot** — copy your **chat ID**
4. Search for your new bot and press **Start**
5. Open the dashboard → **Settings** → paste your token and chat ID → **Save**

You'll now receive phone alerts when CPU, RAM, or disk crosses a threshold, and recovery messages when things return to normal.

---

## Setting Up AI Summaries

Set your Anthropic API key before starting the server:

**Windows:**
```bash
set ANTHROPIC_API_KEY=sk-ant-...
python app.py
```

**Mac/Linux:**
```bash
export ANTHROPIC_API_KEY=sk-ant-...
python app.py
```

The AI summary panel will appear on each device's detail page, refreshing every 5 minutes. If no API key is set, the app falls back to rule-based summaries automatically.

---

## Alert Thresholds (defaults)

| Metric | Warning | Critical |
|--------|---------|----------|
| CPU    | 80%     | 90%      |
| RAM    | 85%     | 95%      |
| Disk   | 85%     | 95%      |
| Offline | — | No check-in for 60s |

All thresholds are configurable in the Settings page. Alerts have a 10-minute cooldown per device to prevent spam.

---

## Anomaly Detection

Beyond simple thresholds, the alert engine detects:

- **Rising RAM trend** — RAM increasing monotonically across 8 samples (possible memory leak)
- **CPU spike** — current CPU is 2 standard deviations above recent baseline
- **Repeated spikes** — 5+ threshold crossings in recent history
- **Offline detection** — no check-in for 60 seconds
- **Recovery** — notifies when a device comes back online

---

## Multi-Device Support

The system is multi-device ready. To monitor additional computers:

1. Copy `agent.py` to the target machine
2. Install dependencies: `pip install psutil requests`
3. Run: `python agent.py --server http://YOUR_MAIN_PC_IP:5000`

Each device gets a unique persistent ID and appears automatically on the dashboard.

---

## Environment Variables

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API key for AI summaries |
| `TELEGRAM_TOKEN` | Telegram bot token |
| `TELEGRAM_CHAT_ID` | Your Telegram chat ID |
| `SYSMON_SERVER` | Server URL for the agent (default: `http://localhost:5000`) |
| `SYSMON_INTERVAL` | Agent polling interval in seconds (default: `10`) |
| `SYSMON_DEVICE_ID` | Override the auto-generated device ID |
| `SECRET_KEY` | Flask secret key (change in production) |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.10+, Flask 3, SQLAlchemy, SQLite |
| Agent | psutil |
| Desktop app | Tkinter, pystray, Pillow, plyer |
| AI summaries | Anthropic Claude API |
| Alerts | Telegram Bot API |
| Web frontend | HTML, CSS, JavaScript, Chart.js |
| Fonts | Segoe UI, Consolas |

---

## Screenshots

> Dashboard overview, device detail with charts, and Telegram alerts running on Windows 10.

---

## Notes

- The SQLite database is created at `instance/sysmon.db` on first run
- Settings are saved to `instance/settings.json`
- The agent retries automatically if the server is unreachable
- All timestamps stored in UTC, displayed in your local time
- The `instance/` folder is excluded from Git (contains your private settings)

---

## License

MIT — free to use, modify, and share.
