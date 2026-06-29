# 📡 NetScan — WiFi & Bluetooth Detector

A radar-console styled desktop web app that scans and displays nearby **WiFi networks** and **Bluetooth devices** in real time. Built with a Python Flask backend and a pure HTML/CSS/JS frontend — no frameworks needed.

> Built by [Ajithram B](https://github.com/ajithram41-cricket) · `Build. Ship. Improve.`

---

## ✨ Features

- 📶 **WiFi scanning** — SSID, BSSID, signal strength (dBm), channel, frequency band, security type
- 🔵 **Bluetooth scanning** — BLE devices (via `bleak`) + paired Classic BT devices (Windows)
- 📡 **Animated radar UI** — live pulsing rings, signal bar indicators, color-coded RSSI
- 🖥️ **Cross-platform** — Windows, Linux, macOS
- 🔁 **Auto-polling** — refreshes scan every 8 seconds automatically
- 📋 **Live scan log** — timestamped event log with color-coded entries
- 💾 **No database** — lightweight, runs fully local

---

## 🖼️ Preview

```
┌─────────────────────────────────────────────────────┐
│  NETSCAN               ● Backend connected           │
├──────────────────────────┬──────────────────────────┤
│  📶 WiFi Networks   [12] │  🔵 Bluetooth Devices [4]│
│   ◎ radar animation      │   ◎ radar animation       │
│  ─────────────────────── │  ───────────────────────  │
│  HomeNetwork_5G  -52 dBm │  JBL Flip 6      ── dBm  │
│  Office_WiFi     -67 dBm │  Galaxy Buds  -71 dBm     │
│  ...                     │  ...                      │
├──────────────────────────┴──────────────────────────┤
│  Scan Log                              [CLEAR LOG]   │
│  [14:32:01] Scan started                             │
│  [14:32:03] Found 12 WiFi network(s)                 │
└─────────────────────────────────────────────────────┘
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.9+
- A WiFi adapter (for WiFi scanning)
- A Bluetooth 4.0+ adapter (for BLE scanning)

### 1. Clone the repo

```bash
git clone https://github.com/ajithram41-cricket/netscan.git
cd netscan
```

### 2. Install dependencies

```bash
pip install flask flask-cors bleak
```

### 3. Run the server

**Windows** — run as Administrator for full BLE support:
```bash
# Right-click → Run as administrator, then:
python server.py
```

**Linux / macOS:**
```bash
python server.py
```

### 4. Open the app

Visit **[http://localhost:5000](http://localhost:5000)** in your browser, then click **Start Scan**.

---

## 📁 Project Structure

```
netscan/
├── server.py        # Flask backend — WiFi & Bluetooth scanning
├── detector.html    # Frontend — radar UI, device lists, scan log
└── README.md
```

---

## 🛠️ How It Works

### Backend (`server.py`)

| OS | WiFi Method | Bluetooth Method |
|----|------------|-----------------|
| Windows | `netsh wlan show networks mode=bssid` | `bleak` (BLE) + PowerShell `Get-PnpDevice` (paired) |
| Linux | `nmcli device wifi list` | `bleak` (BLE) |
| macOS | `airport -s` | `bleak` (BLE) |

- WiFi and Bluetooth scans run in **parallel threads**
- Windows: WLAN AutoConfig service is auto-started if stopped
- Fallback scan mode activates if the primary scan returns 0 networks
- `/health` — backend status check
- `/scan` — returns `{ wifi: [...], bluetooth: [...], errors: [...] }`

### Frontend (`detector.html`)

- Pure HTML/CSS/JS, zero dependencies (Google Fonts only)
- Polls `/scan` every **8 seconds** while scanning is active
- Radar rings animate during active scan, go idle when stopped
- Signal bars: 4 levels based on dBm thresholds (`-55 / -65 / -75`)
- XSS-safe — all device names sanitized via `escHtml()`

---

## ⚠️ Windows Notes

| Issue | Fix |
|-------|-----|
| BLE scan returns nothing | Run `server.py` as **Administrator** |
| WiFi shows 0 networks | Ensure **WLAN AutoConfig** service is running (`services.msc`) |
| bleak not found | `pip install bleak` |
| PowerShell BT error | Run as Administrator; requires Windows 10 v1703+ |

The startup console will tell you if you're missing admin privileges:
```
  Admin    : ✗ NO  ← Run as Administrator for BLE!
```

---

## 📡 API Reference

### `GET /health`
```json
{
  "status": "ok",
  "os": "Windows",
  "admin": true,
  "python": "3.11.x"
}
```

### `GET /scan`
```json
{
  "wifi": [
    {
      "ssid": "HomeNetwork",
      "bssid": "AA:BB:CC:DD:EE:FF",
      "signal": -62,
      "security": "WPA2-Personal",
      "channel": "6",
      "frequency": "2.4"
    }
  ],
  "bluetooth": [
    {
      "name": "JBL Flip 6",
      "address": "11:22:33:44:55:66",
      "type": "BLE",
      "paired": null,
      "rssi": -71
    }
  ],
  "errors": [],
  "os": "Windows",
  "admin": true
}
```

---

## 🧰 Tech Stack

| Layer | Tech |
|-------|------|
| Backend | Python 3, Flask, Flask-CORS |
| BLE | [bleak](https://github.com/hbldh/bleak) |
| WiFi (Win) | `netsh` (built-in) |
| WiFi (Linux) | `nmcli` (NetworkManager) |
| WiFi (macOS) | `airport` (built-in) |
| Frontend | HTML5, CSS3, Vanilla JS |
| Fonts | JetBrains Mono, Inter (Google Fonts) |

---

## 🤝 Contributing

Pull requests welcome. For major changes, open an issue first.

1. Fork the repo
2. Create your branch: `git checkout -b feature/my-feature`
3. Commit: `git commit -m 'Add my feature'`
4. Push: `git push origin feature/my-feature`
5. Open a Pull Request

---
## 👤 Author

**Ajithram**
- GitHub: [@ajithram41-cricket]((https://github.com/ajithram41-cricket))

## 📄 License

MIT License — free to use, modify, and distribute.

---

