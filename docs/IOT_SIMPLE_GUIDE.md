# IP Aqua Tech – Simple IoT First (bago sa web)

Huwag muna i-connect sa Django/Firebase. Sundin ang stages:

| Stage | Goal | File |
|-------|------|------|
| **1** | Basahin sensors → Serial Monitor | `docs/esp32_simple_sensors/esp32_simple_sensors.ino` |
| **2** | Mag-WiFi + print IP | (later) |
| **3** | Send sa Firebase o Django web | `docs/esp32_firebase_example/esp32_firebase_example.ino` |

> **Important:** Bawat sketch ay nasa **sariling folder**. Huwag maglagay ng dalawang `.ino` sa iisang folder — pinagsasama sila ng Arduino IDE at magkaka-error.

---

## Stage 1 – Serial only

### Kailangan

- ESP32 board
- USB cable
- Arduino IDE (o PlatformIO)
- **Optional:** pH / TDS / turbidity sensors  
  Kung wala pa → `USE_MOCK = true` (fake data, OK for demo)

### Setup

1. Arduino IDE → **Boards Manager** → install **esp32** by Espressif
2. Tools → Board → your ESP32
3. Tools → Port → COM port ng board
4. Open `docs/esp32_simple_sensors/esp32_simple_sensors.ino`
5. Iwan muna:

```cpp
const bool USE_MOCK = true;
```

6. Upload
7. **Tools → Serial Monitor** → baud **115200**

### Dapat makita

```
====================================
 IP Aqua Tech – pH / TDS / Turbidity
 Serial only (no WiFi / no web yet)
 Mock sensors: YES
====================================
pH    | TDS(ppm) | Turbidity | Status
--------------------------------------
7.12  |     145  |      0.35 | NORMAL
...
```

Bawat ~2 seconds may bagong line. Kung ganyan → **Stage 1 OK**.

**Sensors muna:** pH, TDS, turbidity lang. (Iba pa later.)

### Real sensors (optional)

1. I-wire ang sensor analog OUT sa mga pin:

| Sensor    | ESP32 pin |
|-----------|-----------|
| pH        | GPIO 34   |
| TDS       | GPIO 35   |
| Turbidity | GPIO 32   |

2. Set:

```cpp
const bool USE_MOCK = false;
```

3. **Calibrate** pH (buffer 4 / 7 / 10) – huwag trust ang raw formula hanggang calibrated.

---

## Stage 2 – WiFi only (optional next)

Kapag stable na ang Serial readings, idadagdag namin:

- Connect to WiFi
- Print `WiFi.localIP()`
- Still **no** web app yet

---

## Stage 3 – Web (Django / Firebase)

Kapag Stage 1–2 OK na:

1. Full sketch: `docs/esp32_firebase_example.ino`
2. Setup guide: `docs/FIREBASE_SETUP.md`
3. Django: `python manage.py runserver` + IoT pages

---

## Four-sensor production sketch

Para sa aktuwal na **DC voltage + pH + TDS + turbidity**, gamitin ang
`docs/esp32_four_sensors/esp32_four_sensors.ino`. Sabay itong nagpapadala sa
Firebase at Django web API. Nasa katabing `README.md` ang wiring, setup, at
calibration instructions.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| No Serial output | Baud 115200? Tama ang COM port? |
| Upload failed | Hold BOOT button while upload, or change cable/port |
| Weird ADC values | Use 3.3V sensors only; add voltage divider if 5V |
| Mock always same-ish | Normal – values slowly random; OK for code test |

---

## Tips for capstone demo

1. Show Serial Monitor first (hardware working)
2. Then show web dashboard (software working)
3. Then connect both (full system)

Stage 1 = proof that IoT hardware/code works **before** web complexity.
