# IP Aqua Tech – Firebase IoT Setup Guide

## Architecture

```
┌─────────────┐     WiFi      ┌──────────────────────┐
│ ESP32 / IoT │ ────────────► │ Firebase Realtime DB │
└─────────────┘               └──────────┬───────────┘
                                         │ Admin SDK sync
                                         ▼
                              ┌──────────────────────┐
                              │   Django (IP Aqua)   │
                              │  models + dashboard  │
                              └──────────────────────┘

Alternative (no Firebase required for sensors):

ESP32 ──POST JSON──► Django /iot/api/ingest/  (X-API-Key)
```

## 1. Create Firebase Project

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. **Add project** → name it e.g. `ip-aqua-tech`
3. Disable Google Analytics if you don’t need it (optional)

## 2. Enable Realtime Database

1. Build → **Realtime Database** → Create Database  
2. Choose region (e.g. `asia-southeast1`)  
3. Start in **test mode** for development (change rules before production)

Suggested temporary rules (dev only):

```json
{
  "rules": {
    ".read": true,
    ".write": true
  }
}
```

Production: lock writes to authenticated devices only.

## 3. Service Account (Django Admin SDK)

1. Project Settings → **Service accounts**  
2. **Generate new private key** → download JSON  
3. Save as:

```
C:\Users\Mateo\OneDrive\Desktop\Capstone\waterfilter-9b08d-firebase-adminsdk-fbsvc-2c9d3dfdbd.json
```

4. Copy your Database URL, e.g.

```
https://ip-aqua-tech-default-rtdb.asia-southeast1.firebasedatabase.app
```

## 4. Configure Django

### Option A – Environment variables (recommended)

PowerShell:

```powershell
$env:FIREBASE_DATABASE_URL = "https://waterfilter-9b08d-default-rtdb.asia-southeast1.firebasedatabase.app"
$env:FIREBASE_CREDENTIALS_PATH = "C:\Users\Mateo\OneDrive\Desktop\Capstone\waterfilter-9b08d-firebase-adminsdk-fbsvc-2c9d3dfdbd.json"
# Optional live browser listeners:
$env:FIREBASE_WEB_API_KEY = "AIza..."
$env:FIREBASE_WEB_AUTH_DOMAIN = "waterfilter-9b08d.firebaseapp.com"
$env:FIREBASE_PROJECT_ID = "waterfilter-9b08d"
$env:FIREBASE_WEB_APP_ID = "1:....:web:...."
python manage.py runserver
```

### Option B – Edit `ipaquatech/settings.py`

Set:

- `FIREBASE_DATABASE_URL`
- `FIREBASE_WEB_*` for browser live mode

## 5. Expected RTDB Structure

```
ipaquatech/
  devices/
    esp32-001/
      name, type, firmware, last_seen
  sensors/
    water_quality/
      latest: { ph, tds, turbidity, flow_rate, water_level, water_level_status, water_dirty, timestamp, device_id }
    solar/
      latest: { panel_voltage, panel_current, power_output, power_consumption, timestamp, device_id }
    battery/
      latest: { voltage, percentage, charging_status, timestamp, device_id }
    tank/
      latest: { level_percent, capacity_liters, timestamp, device_id }
    pump/
      latest: { pump_status, flow_status, water_level_status, water_dirty, level_sensor_fault, timestamp, device_id }
```

## 6. Seed IoT devices

```powershell
.\venv\Scripts\Activate.ps1
python manage.py migrate
python manage.py seed_iot
```

Copy the printed **API Key** into your ESP32 sketch.

## 7. Sync commands

```powershell
# Pull from Firebase → Django
python manage.py sync_firebase

# Local demo without Firebase
python manage.py sync_firebase --demo
```

In the web UI: **IoT / Firebase** → **Sync from Firebase** or **Demo Ingest**.

## 8. ESP32 → Django API (simplest for capstone demo)

```http
POST http://<PC-LAN-IP>:8000/iot/api/ingest/
Content-Type: application/json
X-API-Key: <device api key>

{
  "device_id": "esp32-001",
  "water_quality": {
    "ph": 7.2,
    "tds": 150,
    "turbidity": 0.4,
    "flow_rate": 12,
    "water_level": 60,
    "water_level_status": "MEDIUM",
    "water_dirty": false
  },
  "solar": { "panel_voltage": 28, "panel_current": 8, "power_consumption": 160 },
  "battery": { "voltage": 24.5, "percentage": 80, "charging_status": "CHARGING" },
  "tank": { "level_percent": 70 },
  "pump": { "pump_status": "ON", "flow_status": "ON", "water_level_status": "MEDIUM", "water_dirty": false }
}
```

Sample sketch: `docs/esp32_firebase_example/esp32_firebase_example.ino`
(Requires Library: **ArduinoJson** by Benoit Blanchon)

## 9. Web UI pages

| URL | Purpose |
|-----|---------|
| `/iot/` | IoT dashboard, sync buttons, live snapshot |
| `/iot/devices/` | Device list + API keys |
| `/iot/sync-logs/` | Sync history |

## 10. Security notes

- Never commit `firebase-service-account.json` (already in `.gitignore`)
- Change Firebase rules before public deployment
- Rotate device API keys if leaked
- Use HTTPS in production

## 11. Without Firebase credentials

The system still works:

1. **Demo Ingest** button → simulates sensors  
2. **ESP32 → Django API** with device API key  
3. Dashboard poll mode via `/iot/api/latest/`
