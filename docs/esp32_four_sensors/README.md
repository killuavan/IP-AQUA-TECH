# ESP32 water-quality, tank, pump, and battery controller

`esp32_four_sensors.ino` reads the sensors, controls the pump locally, and
sends live readings to Firebase Realtime Database every 10 seconds. The web
app imports changed Firebase values and stores their history.

## Complete pin map

| Connection | ESP32 pin |
|---|---:|
| pH analog OUT | GPIO34 |
| TDS analog OUT | GPIO35 |
| Turbidity analog OUT | GPIO32 |
| 0-25V battery module S/OUT | GPIO33 |
| Flow sensor signal | GPIO27 |
| Water level LOW + LOW LED | GPIO18 |
| Water level MEDIUM + MEDIUM LED | GPIO19 |
| Water level HIGH + HIGH LED | GPIO21 |
| TIP122 base through 1k resistor | GPIO26 |
| Active buzzer positive | GPIO22 |
| All grounds | ESP32 GND |

The level signal and matching LED share one active-LOW input. LOW starts the
pump, MEDIUM keeps the previous pump state, and HIGH stops the pump. An invalid
level sequence stops the pump for safety. Dirty water and a level-sensor fault
activate the buzzer.

For the automotive relay, connect GPIO26 through 1k to the TIP122 base. Connect
the TIP122 emitter to common GND and collector to relay pin 85. Connect relay
pin 86 to +12V and place a 1N4007 across 85/86 (stripe toward +12V). ESP32 GND
and battery negative must be connected together.

ESP32 inputs must never receive more than 3.3V. The battery code assumes a
common analog 0-25V divider module used with a 12V battery. If your module is
INA219/INA226 or another type, its reader must be changed.

## Setup

1. Install the ESP32 board package in Arduino IDE.
2. Install **ArduinoJson by Benoit Blanchon** from Library Manager.
3. Open `esp32_four_sensors.ino` and confirm WiFi and Firebase settings.
4. Upload, then open Serial Monitor at 115200 baud.
5. Run the web app with `.\venv\Scripts\python.exe manage.py runserver`.

The sketch writes and reads these paths:

```text
ipaquatech/config/thresholds                     (web -> Firebase -> ESP32)
ipaquatech/sensors/water_quality/latest          (ESP32 -> Firebase -> web)
ipaquatech/sensors/pump/latest
ipaquatech/sensors/battery/latest
ipaquatech/devices/esp32-001
```

The ESP32 refreshes adjustable pH, TDS, turbidity, battery, and warning limits
from Firebase every 60 seconds. The web marks a device Offline when it stops
reporting and Error when the level sensor reports an invalid sequence.

An empty `FIREBASE_AUTH_TOKEN` works only while RTDB rules permit the required
reads and writes. Use authenticated, restricted rules before deployment.

## Calibration

- Compare battery voltage with a multimeter and adjust
  `BATTERY_DIVIDER_RATIO` or `BATTERY_VOLTAGE_CALIBRATION`.
- Calibrate pH with buffer solutions.
- Compare TDS with a known calibration solution.
- Measure clear and known-turbid samples for the two turbidity voltages.
- Calibrate `FLOW_PULSE_FACTOR` against a measured water volume.

Raw sensor voltages and final values are printed in Serial Monitor.
