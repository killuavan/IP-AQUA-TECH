/**
 * IP Aqua Tech – ESP32 Multi-Sensor Node
 * Project: waterfilter-9b08d  |  RTDB root: ipaquatech
 *
 * MODE:
 *   USE_FIREBASE = true  → write sensors to Firebase Realtime Database
 *   USE_DJANGO   = true  → also POST to Django /iot/api/ingest/
 *
 * Libraries (Arduino Library Manager / ESP32 board package):
 *   - WiFi, HTTPClient, WiFiClientSecure  (built-in with ESP32)
 *   - ArduinoJson by Benoit Blanchon      (v6 or v7)
 *
 * Firebase rules (dev / demo only):
 *   { "rules": { ".read": true, ".write": true } }
 * Lock rules before real deployment.
 *
 * After flash: open Serial Monitor @ 115200
 * Then on PC:  python manage.py sync_firebase
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>
#include <time.h>
#include "sensor_snapshot.h"

// =============================================================================
// CONFIG – edit these before flash
// =============================================================================

// WiFi
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// Device identity (must match Django IoT device if you use API key)
const char* DEVICE_ID   = "esp32-001";
const char* DEVICE_NAME = "Main Multi-Sensor Node";
const char* FIRMWARE    = "1.1.0";

// Firebase Realtime Database (your project)
const char* FIREBASE_HOST =
  "https://waterfilter-9b08d-default-rtdb.asia-southeast1.firebasedatabase.app";
const char* RTDB_ROOT = "ipaquatech";

// Optional auth query for locked rules (leave empty if rules are open for demo)
// Example: "YOUR_DATABASE_SECRET" or ID token — not needed with open test rules
const char* FIREBASE_AUTH = "";

// Django API (optional backup path)
const char* DJANGO_BASE    = "http://192.168.1.10:8000";  // PC LAN IP
const char* DEVICE_API_KEY = "PASTE_DEVICE_API_KEY_HERE";

// Which paths to use
const bool USE_FIREBASE = true;
const bool USE_DJANGO   = false;   // set true if you also want direct Django ingest

// How often to publish (ms)
const unsigned long SEND_INTERVAL_MS = 15000;
const unsigned long WIFI_RETRY_MS    = 10000;

// NTP (Philippines UTC+8)
const long  GMT_OFFSET_SEC      = 8 * 3600;
const int   DAYLIGHT_OFFSET_SEC = 0;
const char* NTP_SERVER          = "pool.ntp.org";

// =============================================================================
// OPTIONAL real sensor pins (mock mode if USE_MOCK_SENSORS = true)
// =============================================================================
const bool USE_MOCK_SENSORS = true;

// Example pin map – adjust to your wiring
const int PIN_PH_ADC        = 34;  // pH analog
const int PIN_TDS_ADC       = 35;  // TDS analog
const int PIN_TURBIDITY_ADC = 32;
const int PIN_TEMP_DS18B20  = 4;   // OneWire (if you add DallasTemperature later)
const int PIN_FLOW_PULSE    = 27;
const int PIN_PRESSURE_ADC  = 33;
const int PIN_TANK_ADC      = 39;  // ultrasonic / level ADC
const int PIN_PANEL_V_ADC   = 36;
const int PIN_PANEL_A_ADC   = 25;
const int PIN_BATT_V_ADC    = 26;
const int PIN_PUMP_STATUS   = 14;  // digital input or relay feedback
const int PIN_UV_STATUS     = 12;
const int PIN_FLOW_STATUS   = 13;

// =============================================================================
// Internal state
// =============================================================================
unsigned long lastSendMs  = 0;
unsigned long lastWifiMs  = 0;
bool          timeSynced  = false;

// =============================================================================
// Sensor reading helpers
// =============================================================================
float clampf(float v, float lo, float hi) {
  if (v < lo) return lo;
  if (v > hi) return hi;
  return v;
}

float readAdcVoltage(int pin, float vRef = 3.3f) {
  // ESP32 12-bit ADC, attenuation default ~0-3.3V (rough)
  int raw = analogRead(pin);
  return (raw / 4095.0f) * vRef;
}

// ---- Mock or real ----
float readPH() {
  if (USE_MOCK_SENSORS) {
    return clampf(6.8f + (random(0, 60) / 100.0f), 0.0f, 14.0f);
  }
  // Example linear map – calibrate with your pH module
  float v = readAdcVoltage(PIN_PH_ADC);
  return clampf(7.0f + ((1.65f - v) * 3.5f), 0.0f, 14.0f);
}

float readTDS() {
  if (USE_MOCK_SENSORS) return 120.0f + random(0, 80);
  float v = readAdcVoltage(PIN_TDS_ADC);
  // Placeholder conversion – replace with manufacturer formula
  return clampf(v * 500.0f, 0.0f, 2000.0f);
}

float readTurbidity() {
  if (USE_MOCK_SENSORS) return 0.2f + (random(0, 40) / 100.0f);
  float v = readAdcVoltage(PIN_TURBIDITY_ADC);
  return clampf((3.3f - v) * 1.5f, 0.0f, 10.0f);
}

float readTempC() {
  if (USE_MOCK_SENSORS) return 26.0f + (random(0, 40) / 10.0f);
  // Without DS18B20 lib: return ambient estimate from ADC or fixed
  return 28.0f;
}

float readFlowLpm() {
  if (USE_MOCK_SENSORS) return 10.0f + (random(0, 50) / 10.0f);
  // Implement pulse counting on PIN_FLOW_PULSE in ISR for production
  return 0.0f;
}

float readPressureBar() {
  if (USE_MOCK_SENSORS) return 2.0f + (random(0, 20) / 10.0f);
  float v = readAdcVoltage(PIN_PRESSURE_ADC);
  return clampf(v * 2.0f, 0.0f, 10.0f);
}

float readTankLevelPercent() {
  if (USE_MOCK_SENSORS) return clampf(50.0f + random(0, 45), 0.0f, 100.0f);
  float v = readAdcVoltage(PIN_TANK_ADC);
  return clampf((v / 3.3f) * 100.0f, 0.0f, 100.0f);
}

float readPanelVoltage() {
  if (USE_MOCK_SENSORS) return 24.0f + (random(0, 80) / 10.0f);
  // Use voltage divider: panel_V = adc_V * (R1+R2)/R2
  return readAdcVoltage(PIN_PANEL_V_ADC) * 11.0f;
}

float readPanelCurrent() {
  if (USE_MOCK_SENSORS) return 5.0f + (random(0, 50) / 10.0f);
  // ACS712 / INA219 etc.
  return readAdcVoltage(PIN_PANEL_A_ADC) * 5.0f;
}

float readBatteryVoltage() {
  if (USE_MOCK_SENSORS) return 23.5f + (random(0, 20) / 10.0f);
  return readAdcVoltage(PIN_BATT_V_ADC) * 11.0f;
}

float readBatteryPercent() {
  if (USE_MOCK_SENSORS) return clampf(60.0f + random(0, 35), 0.0f, 100.0f);
  // Map 22V–27V pack as 0–100% (24V bank example)
  float v = readBatteryVoltage();
  return clampf(((v - 22.0f) / 5.0f) * 100.0f, 0.0f, 100.0f);
}

const char* readChargingStatus() {
  float pct = readBatteryPercent();
  float panelW = readPanelVoltage() * readPanelCurrent();
  if (panelW > 20.0f && pct < 98.0f) return "CHARGING";
  if (pct >= 98.0f) return "FULL";
  return "DISCHARGING";
}

const char* digOnOff(int pin, bool mockOn) {
  if (USE_MOCK_SENSORS) return mockOn ? "ON" : "OFF";
  pinMode(pin, INPUT_PULLUP);
  // LOW = active (relay feedback) – invert if needed
  return digitalRead(pin) == LOW ? "ON" : "OFF";
}

// =============================================================================
// Time
// =============================================================================
String isoTimestamp() {
  time_t now = time(nullptr);
  if (now < 1600000000) {
    // Not synced yet – use uptime seconds as fallback
    char buf[32];
    snprintf(buf, sizeof(buf), "%lu", (unsigned long)(millis() / 1000UL));
    return String(buf);
  }
  struct tm timeinfo;
  gmtime_r(&now, &timeinfo);  // store UTC ISO; Django accepts ISO
  char buf[40];
  strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", &timeinfo);
  return String(buf);
}

void setupTime() {
  configTime(GMT_OFFSET_SEC, DAYLIGHT_OFFSET_SEC, NTP_SERVER);
  Serial.print("NTP");
  for (int i = 0; i < 20; i++) {
    time_t now = time(nullptr);
    if (now > 1600000000) {
      timeSynced = true;
      Serial.println(" OK");
      Serial.println(isoTimestamp());
      return;
    }
    Serial.print(".");
    delay(500);
  }
  Serial.println(" timeout (will use millis fallback)");
}

// =============================================================================
// WiFi
// =============================================================================
void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.printf("WiFi connecting to %s", WIFI_SSID);

  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 20000UL) {
    delay(400);
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("WiFi OK  IP=");
    Serial.println(WiFi.localIP());
    if (!timeSynced) setupTime();
  } else {
    Serial.println("WiFi FAILED");
  }
  lastWifiMs = millis();
}

// =============================================================================
// HTTP helpers
// =============================================================================
String firebaseAuthQuery() {
  if (FIREBASE_AUTH == nullptr || strlen(FIREBASE_AUTH) == 0) return "";
  return String("?auth=") + FIREBASE_AUTH;
}

bool httpPutJson(const String& url, const String& body) {
  HTTPClient http;
  // RTDB uses HTTPS – ESP32 needs insecure or proper root CA
  WiFiClientSecure client;
  client.setInsecure();  // demo: skip cert verify. Use setCACert() in production.

  if (!http.begin(client, url)) {
    Serial.println("http.begin failed");
    return false;
  }
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(12000);

  int code = http.PUT(body);
  String resp = http.getString();
  Serial.printf("PUT %d %s\n  body: %s\n  resp: %s\n",
                code, url.c_str(), body.c_str(), resp.c_str());
  http.end();
  return code >= 200 && code < 300;
}

bool httpPostJson(const String& url, const String& body, const char* apiKey) {
  HTTPClient http;
  // Django local is usually plain HTTP on LAN
  if (!http.begin(url)) {
    Serial.println("http.begin failed");
    return false;
  }
  http.addHeader("Content-Type", "application/json");
  if (apiKey && strlen(apiKey) > 0) {
    http.addHeader("X-API-Key", apiKey);
  }
  http.setTimeout(12000);

  int code = http.POST(body);
  String resp = http.getString();
  Serial.printf("POST %d %s\n  resp: %s\n", code, url.c_str(), resp.c_str());
  http.end();
  return code >= 200 && code < 300;
}

// =============================================================================
// Build sensor snapshot (type defined in sensor_snapshot.h)
// =============================================================================
SensorSnapshot readAllSensors() {
  SensorSnapshot s;
  s.ph             = readPH();
  s.tds            = readTDS();
  s.turbidity      = readTurbidity();
  s.temperature    = readTempC();
  s.flow_rate      = readFlowLpm();
  s.water_pressure = readPressureBar();
  s.water_level    = readTankLevelPercent();

  s.panel_voltage     = readPanelVoltage();
  s.panel_current     = readPanelCurrent();
  s.power_output      = s.panel_voltage * s.panel_current;
  s.power_consumption = 150.0f + random(0, 40);
  s.irradiance        = 500.0f + random(0, 400);

  s.batt_voltage = readBatteryVoltage();
  s.batt_pct     = readBatteryPercent();
  s.batt_temp    = 28.0f + (random(0, 20) / 10.0f);
  s.charging     = readChargingStatus();

  s.tank_level    = s.water_level;
  s.tank_capacity = 2000.0f;

  s.system_pressure = s.water_pressure;
  s.pump_power      = 160.0f + random(0, 40);
  s.pump_status     = digOnOff(PIN_PUMP_STATUS, true);
  s.uv_status       = digOnOff(PIN_UV_STATUS, true);
  s.flow_status     = digOnOff(PIN_FLOW_STATUS, true);

  s.timestamp = isoTimestamp();
  return s;
}

// =============================================================================
// Firebase writers – paths match Django iot/services.py sync_from_firebase
// =============================================================================
bool putFirebasePath(const char* relativePath, JsonDocument& doc) {
  String url = String(FIREBASE_HOST) + "/" + RTDB_ROOT + "/" + relativePath
             + ".json" + firebaseAuthQuery();
  String body;
  serializeJson(doc, body);
  return httpPutJson(url, body);
}

bool publishFirebase(const SensorSnapshot& s) {
  bool ok = true;

  // devices/{id}
  {
    StaticJsonDocument<384> doc;
    doc["name"]      = DEVICE_NAME;
    doc["type"]      = "MULTI";
    doc["firmware"]  = FIRMWARE;
    doc["last_seen"] = s.timestamp;
    doc["ip"]        = WiFi.localIP().toString();
    String path = String("devices/") + DEVICE_ID;
    ok &= putFirebasePath(path.c_str(), doc);
  }

  // sensors/water_quality/latest
  {
    StaticJsonDocument<512> doc;
    doc["ph"]             = s.ph;
    doc["tds"]            = s.tds;
    doc["turbidity"]      = s.turbidity;
    doc["temperature"]    = s.temperature;
    doc["flow_rate"]      = s.flow_rate;
    doc["water_pressure"] = s.water_pressure;
    doc["water_level"]    = s.water_level;
    doc["device_id"]      = DEVICE_ID;
    doc["timestamp"]      = s.timestamp;
    ok &= putFirebasePath("sensors/water_quality/latest", doc);
  }

  // sensors/solar/latest
  {
    StaticJsonDocument<384> doc;
    doc["panel_voltage"]     = s.panel_voltage;
    doc["panel_current"]     = s.panel_current;
    doc["power_output"]      = s.power_output;
    doc["power_consumption"] = s.power_consumption;
    doc["irradiance"]        = s.irradiance;
    doc["device_id"]         = DEVICE_ID;
    doc["timestamp"]         = s.timestamp;
    ok &= putFirebasePath("sensors/solar/latest", doc);
  }

  // sensors/battery/latest
  {
    StaticJsonDocument<320> doc;
    doc["voltage"]         = s.batt_voltage;
    doc["percentage"]      = s.batt_pct;
    doc["charging_status"] = s.charging;
    doc["temperature"]     = s.batt_temp;
    doc["device_id"]       = DEVICE_ID;
    doc["timestamp"]       = s.timestamp;
    ok &= putFirebasePath("sensors/battery/latest", doc);
  }

  // sensors/tank/latest
  {
    StaticJsonDocument<256> doc;
    doc["level_percent"]   = s.tank_level;
    doc["capacity_liters"] = s.tank_capacity;
    doc["device_id"]       = DEVICE_ID;
    doc["timestamp"]       = s.timestamp;
    ok &= putFirebasePath("sensors/tank/latest", doc);
  }

  // sensors/pump/latest
  {
    StaticJsonDocument<320> doc;
    doc["pump_status"]       = s.pump_status;
    doc["uv_status"]         = s.uv_status;
    doc["flow_status"]       = s.flow_status;
    doc["system_pressure"]   = s.system_pressure;
    doc["power_consumption"] = s.pump_power;
    doc["device_id"]         = DEVICE_ID;
    doc["timestamp"]         = s.timestamp;
    ok &= putFirebasePath("sensors/pump/latest", doc);
  }

  // history push (optional, keeps last samples under history/)
  {
    StaticJsonDocument<256> doc;
    doc["ph"]        = s.ph;
    doc["tds"]       = s.tds;
    doc["tank"]      = s.tank_level;
    doc["batt_pct"]  = s.batt_pct;
    doc["device_id"] = DEVICE_ID;
    doc["timestamp"] = s.timestamp;

    String url = String(FIREBASE_HOST) + "/" + RTDB_ROOT
               + "/history/" + DEVICE_ID + ".json" + firebaseAuthQuery();
    String body;
    serializeJson(doc, body);

    // Use POST to generate a unique child key (push)
    WiFiClientSecure client;
    client.setInsecure();
    HTTPClient http;
    if (http.begin(client, url)) {
      http.addHeader("Content-Type", "application/json");
      int code = http.POST(body);
      Serial.printf("HISTORY POST %d\n", code);
      http.end();
      ok &= (code >= 200 && code < 300);
    }
  }

  return ok;
}

// =============================================================================
// Django API publisher
// =============================================================================
bool publishDjango(const SensorSnapshot& s) {
  StaticJsonDocument<1024> doc;
  doc["device_id"] = DEVICE_ID;

  JsonObject wq = doc.createNestedObject("water_quality");
  wq["ph"]             = s.ph;
  wq["tds"]            = s.tds;
  wq["turbidity"]      = s.turbidity;
  wq["temperature"]    = s.temperature;
  wq["flow_rate"]      = s.flow_rate;
  wq["water_pressure"] = s.water_pressure;
  wq["water_level"]    = s.water_level;
  wq["timestamp"]      = s.timestamp;

  JsonObject solar = doc.createNestedObject("solar");
  solar["panel_voltage"]     = s.panel_voltage;
  solar["panel_current"]     = s.panel_current;
  solar["power_output"]      = s.power_output;
  solar["power_consumption"] = s.power_consumption;
  solar["irradiance"]        = s.irradiance;

  JsonObject batt = doc.createNestedObject("battery");
  batt["voltage"]         = s.batt_voltage;
  batt["percentage"]      = s.batt_pct;
  batt["charging_status"] = s.charging;
  batt["temperature"]     = s.batt_temp;

  JsonObject tank = doc.createNestedObject("tank");
  tank["level_percent"]   = s.tank_level;
  tank["capacity_liters"] = s.tank_capacity;

  JsonObject pump = doc.createNestedObject("pump");
  pump["pump_status"]       = s.pump_status;
  pump["uv_status"]         = s.uv_status;
  pump["flow_status"]       = s.flow_status;
  pump["system_pressure"]   = s.system_pressure;
  pump["power_consumption"] = s.pump_power;

  String body;
  serializeJson(doc, body);

  String url = String(DJANGO_BASE) + "/iot/api/ingest/";
  return httpPostJson(url, body, DEVICE_API_KEY);
}

// =============================================================================
// Main
// =============================================================================
void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println();
  Serial.println("========================================");
  Serial.println(" IP Aqua Tech – ESP32 Sensor Node");
  Serial.printf (" Device : %s\n", DEVICE_ID);
  Serial.printf (" FW     : %s\n", FIRMWARE);
  Serial.printf (" Firebase: %s\n", USE_FIREBASE ? "ON" : "OFF");
  Serial.printf (" Django  : %s\n", USE_DJANGO ? "ON" : "OFF");
  Serial.printf (" Mock    : %s\n", USE_MOCK_SENSORS ? "YES" : "NO");
  Serial.println("========================================");

  randomSeed(esp_random());
  analogReadResolution(12);

  connectWiFi();
}

void loop() {
  // Keep WiFi alive
  if (WiFi.status() != WL_CONNECTED) {
    if (millis() - lastWifiMs >= WIFI_RETRY_MS) {
      connectWiFi();
    }
    delay(200);
    return;
  }

  if (millis() - lastSendMs < SEND_INTERVAL_MS) {
    delay(50);
    return;
  }
  lastSendMs = millis();

  Serial.println("----- sample -----");
  SensorSnapshot s = readAllSensors();
  Serial.printf("pH=%.2f TDS=%.0f NTU=%.2f T=%.1fC tank=%.0f%% batt=%.0f%%\n",
                s.ph, s.tds, s.turbidity, s.temperature, s.tank_level, s.batt_pct);

  bool ok = true;
  if (USE_FIREBASE) {
    Serial.println("Publishing to Firebase...");
    ok &= publishFirebase(s);
  }
  if (USE_DJANGO) {
    Serial.println("Publishing to Django...");
    ok &= publishDjango(s);
  }

  if (!ok) {
    Serial.println("Publish had errors – will retry next cycle");
  } else {
    Serial.println("Publish OK");
  }
}
