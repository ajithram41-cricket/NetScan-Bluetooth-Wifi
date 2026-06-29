"""
NetScan — WiFi & Bluetooth Backend (Windows Fixed v2)
=====================================================
Run AS ADMINISTRATOR for best results on Windows!
  python server.py

Install dependencies:
    pip install flask flask-cors bleak
"""

import subprocess
import platform
import re
import asyncio
import threading
import logging
import json
import ctypes
import sys
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)
CORS(app)

OS = platform.system()   # 'Windows', 'Linux', 'Darwin'

# ─────────────────────────────────────────────────
# ADMIN CHECK (Windows)
# ─────────────────────────────────────────────────

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


# ─────────────────────────────────────────────────
# SERVE FRONTEND
# ─────────────────────────────────────────────────

@app.route("/")
def index():
    try:
        return send_from_directory(".", "detector.html")
    except Exception:
        return (
            "<h2>detector.html not found</h2>"
            "<p>Put <b>detector.html</b> in the same folder as <b>server.py</b>.</p>"
        ), 404


# ─────────────────────────────────────────────────
# WIFI — WINDOWS
# ─────────────────────────────────────────────────

def _run(cmd, timeout=15):
    """Run a subprocess and return stdout or raise."""
    flags = subprocess.CREATE_NO_WINDOW if OS == "Windows" else 0
    return subprocess.check_output(
        cmd, encoding="utf-8", errors="replace",
        timeout=timeout, creationflags=flags,
        stderr=subprocess.STDOUT
    )


def ensure_wlan_service():
    """Start WLAN AutoConfig if not running — needed for netsh to work."""
    try:
        _run(["sc", "query", "wlansvc"], timeout=5)
        # Start it if stopped
        _run(["net", "start", "wlansvc"], timeout=8)
    except Exception:
        pass  # may already be running, that's fine


def scan_wifi_windows():
    networks = []
    debug_lines = []

    # 1) Make sure WLAN service is up
    ensure_wlan_service()

    # 2) Try netsh bssid mode first (most detail)
    try:
        out = _run(["netsh", "wlan", "show", "networks", "mode=bssid"])
        debug_lines.append(f"netsh bssid output length: {len(out)}")

        # Split on each SSID block
        blocks = re.split(r"(?=SSID\s+\d+\s*:)", out)
        for block in blocks:
            ssid_m    = re.search(r"^SSID\s+\d+\s*:\s*(.+)$",            block, re.MULTILINE)
            bssid_m   = re.search(r"BSSID\s+\d+\s*:\s*([\dA-Fa-f:]{17})", block)
            signal_m  = re.search(r"Signal\s*:\s*(\d+)%",                  block)
            auth_m    = re.search(r"Authentication\s*:\s*(.+)",             block)
            channel_m = re.search(r"Channel\s*:\s*(\d+)",                  block)
            radio_m   = re.search(r"Radio type\s*:\s*(.+)",                 block)

            if not bssid_m:
                continue

            pct  = int(signal_m.group(1)) if signal_m else 50
            rssi = round((pct / 2) - 100)

            networks.append({
                "ssid":      ssid_m.group(1).strip() if ssid_m else "(Hidden)",
                "bssid":     bssid_m.group(1).upper(),
                "signal":    rssi,
                "security":  auth_m.group(1).strip()  if auth_m  else "Unknown",
                "channel":   channel_m.group(1)        if channel_m else None,
                "frequency": _radio_to_freq(radio_m.group(1).strip() if radio_m else ""),
            })

        debug_lines.append(f"Parsed {len(networks)} networks from bssid mode")

    except FileNotFoundError:
        debug_lines.append("netsh not found")
    except subprocess.TimeoutExpired:
        debug_lines.append("netsh timed out")
    except Exception as e:
        debug_lines.append(f"netsh bssid error: {e}")

    # 3) Fallback: netsh interface mode (less detail, no BSSID but more compatible)
    if not networks:
        debug_lines.append("Falling back to interface mode scan...")
        try:
            out = _run(["netsh", "wlan", "show", "networks"])
            blocks = re.split(r"(?=SSID\s+\d+\s*:)", out)
            for block in blocks:
                ssid_m    = re.search(r"^SSID\s+\d+\s*:\s*(.+)$",  block, re.MULTILINE)
                auth_m    = re.search(r"Authentication\s*:\s*(.+)",  block)
                signal_m  = re.search(r"Signal\s*:\s*(\d+)%",        block)

                if not ssid_m:
                    continue
                ssid = ssid_m.group(1).strip()
                if not ssid:
                    continue

                pct  = int(signal_m.group(1)) if signal_m else 50
                rssi = round((pct / 2) - 100)

                networks.append({
                    "ssid":      ssid,
                    "bssid":     "N/A",
                    "signal":    rssi,
                    "security":  auth_m.group(1).strip() if auth_m else "Unknown",
                    "channel":   None,
                    "frequency": None,
                })
            debug_lines.append(f"Fallback parsed {len(networks)} networks")
        except Exception as e:
            debug_lines.append(f"Fallback netsh error: {e}")

    for d in debug_lines:
        print(f"[WiFi-Win] {d}")

    return networks


def _radio_to_freq(radio: str) -> str | None:
    """Convert radio type string like '802.11ac' to frequency band."""
    if not radio:
        return None
    r = radio.lower()
    if "802.11a" in r or "802.11ac" in r or "802.11ax" in r or "5ghz" in r:
        return "5.0"
    if "802.11b" in r or "802.11g" in r or "802.11n" in r or "2.4ghz" in r:
        return "2.4"
    return None


# ─────────────────────────────────────────────────
# WIFI — LINUX / macOS (unchanged, working)
# ─────────────────────────────────────────────────

def scan_wifi_linux():
    networks = []
    try:
        out = _run(["nmcli", "-t", "-f", "SSID,BSSID,SIGNAL,SECURITY,CHAN,FREQ",
                    "device", "wifi", "list", "--rescan", "yes"])
        for line in out.strip().splitlines():
            parts = re.split(r"(?<!\\):", line)
            if len(parts) < 5:
                continue
            bssid = parts[1].replace("\\:", ":").upper()
            try:
                rssi = round((int(parts[2]) / 2) - 100)
            except ValueError:
                rssi = -80
            fm = re.search(r"([\d.]+)\s*GHz", parts[5] if len(parts) > 5 else "", re.I)
            networks.append({
                "ssid":      parts[0].replace("\\:", ":").strip(),
                "bssid":     bssid,
                "signal":    rssi,
                "security":  parts[3].strip() or "Open",
                "channel":   parts[4].strip() or None,
                "frequency": fm.group(1) if fm else None,
            })
    except Exception as e:
        print(f"[WiFi-Linux] {e}")
    return networks


def scan_wifi_macos():
    networks = []
    airport = (
        "/System/Library/PrivateFrameworks/Apple80211.framework"
        "/Versions/Current/Resources/airport"
    )
    try:
        out = _run([airport, "-s"])
        for line in out.strip().splitlines()[1:]:
            parts = line.split()
            if len(parts) < 4:
                continue
            bssid_idx = next(
                (i for i, p in enumerate(parts)
                 if re.match(r"[\da-f]{2}:[\da-f]{2}:", p, re.I)), None
            )
            if bssid_idx is None:
                continue
            ssid    = " ".join(parts[:bssid_idx])
            bssid   = parts[bssid_idx].upper()
            try:
                rssi    = int(parts[bssid_idx + 1])
                channel = parts[bssid_idx + 2]
            except (ValueError, IndexError):
                rssi, channel = -80, None
            networks.append({
                "ssid":      ssid,
                "bssid":     bssid,
                "signal":    rssi,
                "security":  " ".join(parts[bssid_idx + 4:]) or "Open",
                "channel":   channel,
                "frequency": "5.0" if channel and int(re.sub(r"\D", "", channel) or 0) > 14 else "2.4",
            })
    except Exception as e:
        print(f"[WiFi-macOS] {e}")
    return networks


def scan_wifi():
    if OS == "Windows": return scan_wifi_windows()
    if OS == "Linux":   return scan_wifi_linux()
    if OS == "Darwin":  return scan_wifi_macos()
    return []


# ─────────────────────────────────────────────────
# BLUETOOTH — BLE via bleak
# ─────────────────────────────────────────────────

def scan_bt_bleak():
    devices = []
    try:
        from bleak import BleakScanner

        async def _scan():
            # return_adv=True gives richer data including RSSI
            return await BleakScanner.discover(timeout=8.0, return_adv=True)

        # Windows MUST use ProactorEventLoop for BLE
        if OS == "Windows":
            loop = asyncio.ProactorEventLoop()
        else:
            loop = asyncio.new_event_loop()

        asyncio.set_event_loop(loop)
        try:
            results = loop.run_until_complete(_scan())
        finally:
            loop.close()
            asyncio.set_event_loop(None)

        for addr, (device, adv) in results.items():
            devices.append({
                "name":    device.name or adv.local_name or "Unknown BLE",
                "address": device.address.upper(),
                "type":    "BLE",
                "paired":  None,
                "rssi":    adv.rssi,
            })

        print(f"[BT-BLE] Found {len(devices)} BLE devices")

    except ImportError:
        print("[BT] bleak not installed — run: pip install bleak")
        devices.append({
            "name":    "⚠ bleak not installed",
            "address": "pip install bleak",
            "type":    "BLE",
            "paired":  None,
            "rssi":    None,
        })
    except Exception as e:
        err = str(e)
        print(f"[BT-BLE] Error: {err}")

        # Friendly hints for common Windows BLE errors
        hint = None
        if "Access" in err or "0x8007005" in err:
            hint = "⚠ BLE access denied — run server.py as Administrator"
        elif "not found" in err.lower() or "adapter" in err.lower():
            hint = "⚠ No Bluetooth adapter found or adapter is off"
        elif "WinRT" in err or "winrt" in err.lower():
            hint = "⚠ Windows BLE requires Windows 10 v1703+ and a Bluetooth 4.0+ adapter"

        if hint:
            devices.append({
                "name": hint, "address": "Check console for details",
                "type": "BLE", "paired": None, "rssi": None,
            })

    return devices


# ─────────────────────────────────────────────────
# BLUETOOTH — Windows paired devices via PowerShell
# ─────────────────────────────────────────────────

def scan_bt_windows_paired():
    devices = []
    try:
        # Broader query — include non-OK status too, so we catch more devices
        ps_cmd = (
            "Get-PnpDevice -Class Bluetooth | "
            "Select-Object FriendlyName, Status, InstanceId | "
            "ConvertTo-Json -Depth 2"
        )
        out = _run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd], timeout=12)
        out = out.strip()

        if not out:
            print("[BT-Win-Paired] PowerShell returned empty output")
            return devices

        # Strip BOM / non-JSON preamble if present
        json_start = out.find("[")
        if json_start == -1:
            json_start = out.find("{")
        if json_start > 0:
            out = out[json_start:]

        data = json.loads(out)
        if isinstance(data, dict):
            data = [data]

        for item in data:
            name   = item.get("FriendlyName") or "Unknown BT Device"
            status = item.get("Status", "")
            iid    = item.get("InstanceId", "")

            # Skip generic Bluetooth radio entries (not real peripheral devices)
            if "BTHENUM" not in iid and "BTH" not in iid and "BLUETOOTH" not in iid.upper():
                continue

            # Try to extract MAC address from InstanceId
            # InstanceId format: BTHENUM\DEV_AABBCCDDEEFF or similar
            mac_m = re.search(r"DEV_([0-9A-Fa-f]{12})", iid)
            if mac_m:
                raw = mac_m.group(1)
                mac = ":".join(raw[i:i+2] for i in range(0, 12, 2)).upper()
            else:
                # Last-ditch: grab any 12-hex-char sequence
                hex_m = re.search(r"([0-9A-Fa-f]{12})", iid.replace("_", ""))
                if hex_m:
                    raw = hex_m.group(1)
                    mac = ":".join(raw[i:i+2] for i in range(0, 12, 2)).upper()
                else:
                    mac = "N/A"

            devices.append({
                "name":    name,
                "address": mac,
                "type":    f"Classic BT ({status})",
                "paired":  status == "OK",
                "rssi":    None,
            })

        print(f"[BT-Win-Paired] Found {len(devices)} paired devices")

    except subprocess.TimeoutExpired:
        print("[BT-Win-Paired] PowerShell timed out")
    except json.JSONDecodeError as e:
        print(f"[BT-Win-Paired] JSON parse error: {e}")
    except Exception as e:
        print(f"[BT-Win-Paired] {e}")

    return devices


def scan_bluetooth():
    paired, ble = [], []

    if OS == "Windows":
        # Run both in parallel
        def _do_paired(): nonlocal paired; paired = scan_bt_windows_paired()
        def _do_ble():    nonlocal ble;    ble    = scan_bt_bleak()
        t1 = threading.Thread(target=_do_paired, daemon=True)
        t2 = threading.Thread(target=_do_ble,    daemon=True)
        t1.start(); t2.start()
        t1.join(timeout=15)
        t2.join(timeout=15)
    else:
        ble = scan_bt_bleak()

    # Merge, deduplicate by address
    seen   = {d["address"] for d in ble}
    merged = list(ble)
    for d in paired:
        if d["address"] not in seen:
            merged.append(d)
            seen.add(d["address"])

    return merged


# ─────────────────────────────────────────────────
# FLASK ROUTES
# ─────────────────────────────────────────────────

@app.route("/health")
def health():
    info = {
        "status": "ok",
        "os": OS,
        "admin": is_admin() if OS == "Windows" else None,
        "python": sys.version,
    }
    return jsonify(info)


@app.route("/scan")
def scan():
    wifi_result, bt_result, errors = [], [], []

    def do_wifi():
        nonlocal wifi_result
        try:
            wifi_result = scan_wifi()
        except Exception as e:
            errors.append(f"WiFi: {e}")

    def do_bt():
        nonlocal bt_result
        try:
            bt_result = scan_bluetooth()
        except Exception as e:
            errors.append(f"BT: {e}")

    t1 = threading.Thread(target=do_wifi, daemon=True)
    t2 = threading.Thread(target=do_bt,   daemon=True)
    t1.start(); t2.start()
    t1.join(timeout=25)
    t2.join(timeout=25)

    for err in errors:
        print(f"[Scan Error] {err}")

    return jsonify({
        "wifi":      wifi_result,
        "bluetooth": bt_result,
        "errors":    errors,
        "os":        OS,
        "admin":     is_admin() if OS == "Windows" else None,
    })


# ─────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────

if __name__ == "__main__":
    admin = is_admin() if OS == "Windows" else True
    print("=" * 56)
    print("  NetScan Backend — Windows Fixed v2")
    print(f"  OS       : {OS}")
    print(f"  Admin    : {'✓ YES' if admin else '✗ NO  ← Run as Administrator for BLE!'}")
    print("  URL      : http://localhost:5000")
    print("=" * 56)
    if OS == "Windows" and not admin:
        print()
        print("  ⚠  WARNING: Not running as Administrator.")
        print("     WiFi will work, but BLE scanning may fail.")
        print("     Right-click server.py → 'Run as administrator'")
        print("     or start CMD as admin then: python server.py")
        print()
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
