/**
 * IP Aqua Tech - ESP32 water-quality and tank controller
 *
 * Sensors: flow, pH, TDS, turbidity, battery voltage, and tank-level switches.
 * LOW starts the pump, MEDIUM keeps its previous state, and HIGH stops it.
 * Dirty water or an invalid level-sensor sequence activates the buzzer.
 * Sends every sample to Firebase RTDB. Django then listens to Firebase and
 * saves the readings in the Monitoring database.
 * Install "ArduinoJson by Benoit Blanchon" in Arduino Library Manager.
 *
 * COMPLETE ESP32 PIN MAP
 * ---------------------------------------------------------------------------
 * pH sensor analog OUT       -> GPIO34
 * TDS sensor analog OUT      -> GPIO35
 * Turbidity sensor analog OUT-> GPIO32
 * Battery voltage module S/OUT-> GPIO33
 * Flow sensor pulse/signal   -> GPIO27
 * Water-level LOW + LOW LED  -> GPIO18 (shared active-LOW signal)
 * Water-level MED + MED LED  -> GPIO19 (shared active-LOW signal)
 * Water-level HIGH + HIGH LED-> GPIO21 (shared active-LOW signal)
 * TIP122 Base                -> GPIO26 through 1k resistor
 * Active buzzer positive     -> GPIO22
 * All sensor/LED grounds     -> ESP32 GND
 * ---------------------------------------------------------------------------
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>
#include <time.h>

// =============================================================================
// REQUIRED CONFIGURATION - replace before uploading
// =============================================================================

const char* WIFI_SSID     = "100MBPS";
const char* WIFI_PASSWORD = "Capstone4F4";

const char* DEVICE_ID = "esp32-001";

const char* FIREBASE_DATABASE_URL =
  "https://waterfilter-9b08d-default-rtdb.asia-southeast1.firebasedatabase.app";
const char* FIREBASE_ROOT = "ipaquatech";

// Empty only works while RTDB rules permit unauthenticated writes.
const char* FIREBASE_AUTH_TOKEN = "";

const bool SEND_TO_FIREBASE = true;

// =============================================================================
// WIRING
// =============================================================================

const int PIN_PH         = 34;
const int PIN_TDS        = 35;
const int PIN_TURBIDITY  = 32;
const int PIN_BATTERY    = 33;
const int PIN_FLOW       = 27;

// Level switches/probe modules close to GND when wet (active LOW).
const int PIN_LEVEL_LOW  = 18;
const int PIN_LEVEL_MED  = 19;
const int PIN_LEVEL_HIGH = 21;

const int PIN_PUMP_RELAY = 26;
const int PIN_BUZZER     = 22;

const bool LEVEL_SENSOR_ACTIVE_LOW = true;
// GPIO26 drives a TIP122 base, so HIGH energizes the automotive relay.
const bool PUMP_RELAY_ACTIVE_LOW   = false;
const bool BUZZER_ACTIVE_HIGH      = true;

// Each shared level/LED line:
// 3.3V -> 220-330 ohm resistor -> LED anode; LED cathode -> GPIO/sensor line
// GPIO/sensor line -> active-LOW level switch/module -> GND
// The LED is hardware-driven by the wet sensor; the GPIO remains INPUT_PULLUP.

// Automotive relay driver wiring:
// GPIO26 -> 1k resistor -> TIP122 Base (pin 1)
// TIP122 Base -> 10k resistor -> GND (keeps relay off during reset)
// TIP122 Emitter (pin 3) -> GND
// TIP122 Collector (pin 2 / metal tab) -> relay coil negative
// Relay coil positive -> +12V
// 1N4007 across coil: cathode/stripe to +12V, anode to TIP122 Collector
// ESP32 GND and 12V supply negative must be connected together.

// Never allow more than 3.3V at any ESP32 GPIO input.

// =============================================================================
// CALIBRATION
// =============================================================================

const float ADC_REFERENCE_V = 3.30f;
const int ADC_MAX = 4095;
const int ADC_SAMPLES = 20;

// YF-S201 default: frequency (Hz) = 7.5 x flow (L/min).
// Change this value to match the calibration sheet of your flow sensor.
const float FLOW_PULSE_FACTOR = 7.50f;

// Enter the voltage measured in pH 7 buffer. Reverse slope sign if necessary.
const float PH7_VOLTAGE = 1.65f;
const float PH_SLOPE    = -3.50f;

// Fixed compensation temperature because no temperature sensor was specified.
const float WATER_TEMPERATURE_C = 25.0f;
const float TDS_CALIBRATION     = 1.00f;

// Replace with module voltages measured in clear and known 10 NTU samples.
const float TURBIDITY_CLEAR_V = 2.80f;
const float TURBIDITY_10NTU_V = 0.80f;
// Generic 0-25V voltage-divider module: module S/OUT -> GPIO33, - -> GND,
// + -> 12V battery positive. ESP32 GND and battery negative must be common.
// Verify the module ratio with a multimeter and tune these two values.
const float BATTERY_DIVIDER_RATIO = 5.00f;
const float BATTERY_VOLTAGE_CALIBRATION = 1.00f;

// Runtime thresholds. Defaults work offline and are replaced by
// /ipaquatech/config/thresholds from Firebase when WiFi is available.
float phNormalMin = 6.5f;
float phNormalMax = 8.5f;
float phDangerMin = 6.0f;
float phDangerMax = 9.0f;
float tdsNormalMax = 300.0f;
float tdsDangerMax = 500.0f;
float turbidityNormalMax = 1.0f;
float turbidityDangerMax = 5.0f;
float batteryWarningPercent = 30.0f;
float batteryCriticalPercent = 15.0f;
float batteryEmptyVoltage = 11.8f;
float batteryFullVoltage = 12.7f;

const unsigned long SEND_INTERVAL_MS = 600000UL;
const unsigned long WIFI_RETRY_MS    = 10000UL;
const unsigned long THRESHOLD_SYNC_INTERVAL_MS = 60000UL;
const unsigned long PUMP_MAX_RUNTIME_MS = 30UL * 60UL * 1000UL;
const unsigned long PUMP_RETRY_DELAY_MS = 2UL * 60UL * 60UL * 1000UL;

unsigned long lastSendMs = 0;
unsigned long lastWiFiAttemptMs = 0;
unsigned long lastFlowMeasurementMs = 0;
unsigned long lastThresholdSyncMs = 0;
volatile unsigned long flowPulseCount = 0;
bool wifiWasConnected = false;
volatile bool pumpOn = false;
volatile bool dirtyWaterAlarm = false;
volatile bool levelSensorFault = false;
unsigned long pumpStartedMs = 0;
unsigned long pumpCooldownUntilMs = 0;

enum WaterLevelState {
  LEVEL_LOW,
  LEVEL_MEDIUM,
  LEVEL_HIGH,
  LEVEL_SENSOR_FAULT,
};

volatile WaterLevelState waterLevelState = LEVEL_LOW;

struct SensorReading {
  float flowRate;
  float ph;
  float tds;
  float turbidity;
  float rawPhVoltage;
  float rawTdsVoltage;
  float rawTurbidityVoltage;
  int waterLevelPercent;
  String waterLevelStatus;
  bool pumpOn;
  bool dirtyWater;
  bool levelSensorFault;
  float batteryVoltage;
  float batteryPercent;
  String batteryStatus;
  String chargingStatus;
  String warningLevel;
  String systemStatus;
  String timestamp;
};

float clampValue(float value, float minimum, float maximum) {
  if (value < minimum) return minimum;
  if (value > maximum) return maximum;
  return value;
}

bool inputIsActive(int pin, bool activeLow) {
  return digitalRead(pin) == (activeLow ? LOW : HIGH);
}

void setOutputActive(int pin, bool active, bool activeLow) {
  digitalWrite(pin, active == activeLow ? LOW : HIGH);
}

const char* waterLevelText(WaterLevelState state) {
  switch (state) {
    case LEVEL_LOW: return "LOW";
    case LEVEL_MEDIUM: return "MEDIUM";
    case LEVEL_HIGH: return "HIGH";
    default: return "SENSOR_FAULT";
  }
}

int waterLevelPercent(WaterLevelState state) {
  switch (state) {
    case LEVEL_LOW: return 25;
    case LEVEL_MEDIUM: return 60;
    case LEVEL_HIGH: return 100;
    default: return 0;
  }
}

void updateWaterControl() {
  bool lowWet = inputIsActive(PIN_LEVEL_LOW, LEVEL_SENSOR_ACTIVE_LOW);
  bool mediumWet = inputIsActive(PIN_LEVEL_MED, LEVEL_SENSOR_ACTIVE_LOW);
  bool highWet = inputIsActive(PIN_LEVEL_HIGH, LEVEL_SENSOR_ACTIVE_LOW);

  // A higher probe cannot validly be wet while a lower probe is dry.
  levelSensorFault = (mediumWet && !lowWet) || (highWet && (!mediumWet || !lowWet));

  time_t currentTime = time(nullptr);
  struct tm localTimeInfo;
  bool clockValid = currentTime >= 1600000000
    && localtime_r(&currentTime, &localTimeInfo) != nullptr;
  bool insidePumpWindow = clockValid
    && (localTimeInfo.tm_hour >= 6 && localTimeInfo.tm_hour < 20);
  unsigned long nowMs = millis();

  if (levelSensorFault) {
    waterLevelState = LEVEL_SENSOR_FAULT;
    pumpOn = false;  // Fail-safe: never keep filling with unreliable level data.
  } else if (highWet) {
    waterLevelState = LEVEL_HIGH;
    if (pumpOn) pumpCooldownUntilMs = nowMs + PUMP_RETRY_DELAY_MS;
    pumpOn = false;
  } else if (mediumWet) {
    waterLevelState = LEVEL_MEDIUM;
    // Continue filling at medium only while the current timed run is active.
  } else {
    waterLevelState = LEVEL_LOW;
  }

  if (pumpOn && (!insidePumpWindow
      || nowMs - pumpStartedMs >= PUMP_MAX_RUNTIME_MS)) {
    if (insidePumpWindow) pumpCooldownUntilMs = nowMs + PUMP_RETRY_DELAY_MS;
    pumpOn = false;
  }
  bool cooldownActive = pumpCooldownUntilMs != 0
    && (int32_t)(nowMs - pumpCooldownUntilMs) < 0;
  if (!pumpOn && !levelSensorFault && !highWet && !mediumWet
      && insidePumpWindow && !cooldownActive) {
    pumpOn = true;
    pumpStartedMs = nowMs;
  }

  // Level LEDs are wired directly to these active-LOW sensor lines, so they
  // indicate the wet probes without using separate ESP32 output pins.
  setOutputActive(PIN_PUMP_RELAY, pumpOn, PUMP_RELAY_ACTIVE_LOW);

  bool alarm = dirtyWaterAlarm || levelSensorFault;
  bool buzzerPulse = alarm && ((millis() / 300UL) % 2UL == 0UL);
  setOutputActive(PIN_BUZZER, buzzerPulse, !BUZZER_ACTIVE_HIGH);
}

void waterControlTask(void* parameter) {
  // This keeps LOW/HIGH pump protection responsive even while an HTTPS
  // Firebase request is waiting or timing out in the main Arduino loop.
  for (;;) {
    updateWaterControl();
    vTaskDelay(pdMS_TO_TICKS(50));
  }
}

float readAverageAdcVoltage(int pin) {
  uint32_t total = 0;
  for (int i = 0; i < ADC_SAMPLES; i++) {
    total += analogRead(pin);
    delay(3);
  }
  float averageRaw = total / (float)ADC_SAMPLES;
  return (averageRaw / ADC_MAX) * ADC_REFERENCE_V;
}

void IRAM_ATTR countFlowPulse() {
  flowPulseCount++;
}

float readFlowRate() {
  unsigned long nowMs = millis();
  unsigned long elapsedMs = nowMs - lastFlowMeasurementMs;
  noInterrupts();
  unsigned long pulses = flowPulseCount;
  flowPulseCount = 0;
  interrupts();
  lastFlowMeasurementMs = nowMs;

  if (elapsedMs == 0 || FLOW_PULSE_FACTOR <= 0.0f) return 0.0f;
  float frequencyHz = (pulses * 1000.0f) / elapsedMs;
  return clampValue(frequencyHz / FLOW_PULSE_FACTOR, 0.0f, 100.0f);
}

float calculatePH(float sensorVoltage) {
  float ph = 7.0f + ((sensorVoltage - PH7_VOLTAGE) * PH_SLOPE);
  return clampValue(ph, 0.0f, 14.0f);
}

float calculateTDS(float sensorVoltage) {
  float compensation = 1.0f + 0.02f * (WATER_TEMPERATURE_C - 25.0f);
  float v = sensorVoltage / compensation;
  float tds = (133.42f * v * v * v - 255.86f * v * v + 857.39f * v)
            * 0.5f * TDS_CALIBRATION;
  return clampValue(tds, 0.0f, 2000.0f);
}

float calculateTurbidity(float sensorVoltage) {
  float span = TURBIDITY_CLEAR_V - TURBIDITY_10NTU_V;
  if (span <= 0.01f) return 0.0f;
  float ntu = ((TURBIDITY_CLEAR_V - sensorVoltage) / span) * 10.0f;
  return clampValue(ntu, 0.0f, 10.0f);
}

float readBatteryVoltage() {
  float moduleOutput = readAverageAdcVoltage(PIN_BATTERY);
  return moduleOutput * BATTERY_DIVIDER_RATIO * BATTERY_VOLTAGE_CALIBRATION;
}

int highWarningScore(float value, float normalMax, float dangerMax) {
  if (value > dangerMax) return 3;
  if (value <= normalMax) return 0;
  float midpoint = normalMax + ((dangerMax - normalMax) / 2.0f);
  return value > midpoint ? 2 : 1;
}

String calculateWarningLevel(float ph, float tds, float turbidity) {
  int score = 0;
  if (ph < phDangerMin || ph > phDangerMax) {
    score = 3;
  } else if (ph < phNormalMin) {
    float midpoint = (phDangerMin + phNormalMin) / 2.0f;
    score = ph < midpoint ? 2 : 1;
  } else if (ph > phNormalMax) {
    float midpoint = (phNormalMax + phDangerMax) / 2.0f;
    score = ph > midpoint ? 2 : 1;
  }
  score = max(score, highWarningScore(tds, tdsNormalMax, tdsDangerMax));
  score = max(score, highWarningScore(turbidity, turbidityNormalMax, turbidityDangerMax));
  if (score == 3) return "DANGER";
  if (score == 2) return "MIDDLE";
  if (score == 1) return "FIRST";
  return "NORMAL";
}

String isoTimestamp() {
  time_t now = time(nullptr);
  if (now < 1600000000) return String((unsigned long)(millis() / 1000UL));
  struct tm utc;
  gmtime_r(&now, &utc);
  char output[30];
  strftime(output, sizeof(output), "%Y-%m-%dT%H:%M:%SZ", &utc);
  return String(output);
}

SensorReading readSensors() {
  SensorReading reading;
  reading.rawPhVoltage = readAverageAdcVoltage(PIN_PH);
  reading.rawTdsVoltage = readAverageAdcVoltage(PIN_TDS);
  reading.rawTurbidityVoltage = readAverageAdcVoltage(PIN_TURBIDITY);
  reading.flowRate = readFlowRate();
  reading.ph = calculatePH(reading.rawPhVoltage);
  reading.tds = calculateTDS(reading.rawTdsVoltage);
  reading.turbidity = calculateTurbidity(reading.rawTurbidityVoltage);
  reading.dirtyWater = reading.turbidity > turbidityNormalMax;
  reading.warningLevel = calculateWarningLevel(
    reading.ph, reading.tds, reading.turbidity
  );
  reading.batteryVoltage = readBatteryVoltage();
  float batterySpan = batteryFullVoltage - batteryEmptyVoltage;
  reading.batteryPercent = batterySpan > 0.01f
    ? clampValue(
        ((reading.batteryVoltage - batteryEmptyVoltage) / batterySpan) * 100.0f,
        0.0f, 100.0f
      )
    : 0.0f;
  reading.batteryStatus = reading.batteryPercent <= batteryCriticalPercent
    ? "CRITICAL"
    : reading.batteryPercent <= batteryWarningPercent ? "WARNING" : "NORMAL";
  reading.chargingStatus = reading.batteryVoltage >= 13.0f
    ? "CHARGING"
    : reading.batteryPercent >= 99.0f ? "FULL" : "DISCHARGING";
  dirtyWaterAlarm = reading.dirtyWater;
  updateWaterControl();
  reading.waterLevelPercent = waterLevelPercent(waterLevelState);
  reading.waterLevelStatus = waterLevelText(waterLevelState);
  reading.pumpOn = pumpOn;
  reading.levelSensorFault = levelSensorFault;
  reading.systemStatus = reading.levelSensorFault ? "ERROR" : "NORMAL";
  reading.timestamp = isoTimestamp();
  return reading;
}

void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  lastWiFiAttemptMs = millis();
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.printf("Connecting to WiFi: %s\n", WIFI_SSID);
}

void maintainWiFi() {
  bool connected = WiFi.status() == WL_CONNECTED;
  if (connected && !wifiWasConnected) {
    Serial.print("WiFi connected. ESP32 IP: ");
    Serial.println(WiFi.localIP());
    configTime(8 * 3600, 0, "pool.ntp.org", "time.google.com");
  } else if (!connected && wifiWasConnected) {
    Serial.println("WiFi disconnected; tank control remains active offline.");
  }
  wifiWasConnected = connected;

  if (!connected && millis() - lastWiFiAttemptMs >= WIFI_RETRY_MS) connectWiFi();
}

String firebaseAuthQuery() {
  if (strlen(FIREBASE_AUTH_TOKEN) == 0) return "";
  return String("?auth=") + FIREBASE_AUTH_TOKEN;
}

bool firebasePut(const String& relativePath, JsonDocument& document) {
  String url = String(FIREBASE_DATABASE_URL) + "/" + FIREBASE_ROOT + "/"
             + relativePath + ".json" + firebaseAuthQuery();
  String body;
  serializeJson(document, body);
  WiFiClientSecure secureClient;
  secureClient.setInsecure(); // Demo only; use a root CA in production.
  HTTPClient http;
  if (!http.begin(secureClient, url)) return false;
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(12000);
  int statusCode = http.PUT(body);
  String response = http.getString();
  http.end();
  Serial.printf("Firebase PUT %s: HTTP %d %s\n",
                relativePath.c_str(), statusCode, response.c_str());
  return statusCode >= 200 && statusCode < 300;
}

bool loadThresholdsFromFirebase() {
  String url = String(FIREBASE_DATABASE_URL) + "/" + FIREBASE_ROOT
             + "/config/thresholds.json" + firebaseAuthQuery();
  WiFiClientSecure secureClient;
  secureClient.setInsecure(); // Demo only; use a root CA in production.
  HTTPClient http;
  if (!http.begin(secureClient, url)) return false;
  http.setTimeout(12000);
  int statusCode = http.GET();
  if (statusCode < 200 || statusCode >= 300) {
    Serial.printf("Firebase threshold GET: HTTP %d\n", statusCode);
    http.end();
    return false;
  }

  DynamicJsonDocument document(1536);
  DeserializationError error = deserializeJson(document, http.getString());
  http.end();
  if (error) {
    Serial.printf("Threshold JSON error: %s\n", error.c_str());
    return false;
  }

  phNormalMin = document["ph"]["min_normal"] | phNormalMin;
  phNormalMax = document["ph"]["max_normal"] | phNormalMax;
  phDangerMin = document["ph"]["min_warning"] | phDangerMin;
  phDangerMax = document["ph"]["max_warning"] | phDangerMax;
  tdsNormalMax = document["tds"]["max_normal"] | tdsNormalMax;
  tdsDangerMax = document["tds"]["max_warning"] | tdsDangerMax;
  turbidityNormalMax = document["turbidity"]["max_normal"] | turbidityNormalMax;
  turbidityDangerMax = document["turbidity"]["max_warning"] | turbidityDangerMax;
  batteryWarningPercent = document["battery"]["low_warning"] | batteryWarningPercent;
  batteryCriticalPercent = document["battery"]["low_critical"] | batteryCriticalPercent;
  batteryEmptyVoltage = document["battery"]["empty_voltage"] | batteryEmptyVoltage;
  batteryFullVoltage = document["battery"]["full_voltage"] | batteryFullVoltage;
  Serial.println("Monitoring thresholds updated from Firebase.");
  return true;
}

bool sendToFirebase(const SensorReading& reading) {
  bool success = true;
  {
    StaticJsonDocument<384> document;
    document["ph"] = reading.ph;
    document["tds"] = reading.tds;
    document["turbidity"] = reading.turbidity;
    document["flow_rate"] = reading.flowRate;
    document["water_level"] = reading.waterLevelPercent;
    document["water_level_status"] = reading.waterLevelStatus;
    document["water_dirty"] = reading.dirtyWater;
    document["level_sensor_fault"] = reading.levelSensorFault;
    document["warning_level"] = reading.warningLevel;
    document["device_id"] = DEVICE_ID;
    document["timestamp"] = reading.timestamp;
    success &= firebasePut("sensors/water_quality/latest", document);
  }
  {
    StaticJsonDocument<320> document;
    document["pump_status"] = reading.pumpOn ? "ON" : "OFF";
    document["flow_status"] = reading.flowRate > 0.1f ? "ON" : "OFF";
    document["water_level"] = reading.waterLevelPercent;
    document["water_level_status"] = reading.waterLevelStatus;
    document["water_dirty"] = reading.dirtyWater;
    document["level_sensor_fault"] = reading.levelSensorFault;
    document["device_id"] = DEVICE_ID;
    document["timestamp"] = reading.timestamp;
    success &= firebasePut("sensors/pump/latest", document);
  }
  {
    StaticJsonDocument<320> document;
    document["voltage"] = reading.batteryVoltage;
    document["percentage"] = reading.batteryPercent;
    document["status"] = reading.batteryStatus;
    document["charging_status"] = reading.chargingStatus;
    document["device_id"] = DEVICE_ID;
    document["timestamp"] = reading.timestamp;
    success &= firebasePut("sensors/battery/latest", document);
  }
  {
    StaticJsonDocument<256> document;
    document["name"] = "Water Quality and Tank Controller";
    document["type"] = "MULTI";
    document["firmware"] = "4.1.0-tank-battery-controller";
    document["last_seen"] = reading.timestamp;
    document["ip"] = WiFi.localIP().toString();
    document["status"] = reading.systemStatus;
    success &= firebasePut(String("devices/") + DEVICE_ID, document);
  }
  return success;
}

void setup() {
  Serial.begin(115200);
  delay(700);

  digitalWrite(PIN_PUMP_RELAY, PUMP_RELAY_ACTIVE_LOW ? HIGH : LOW);
  pinMode(PIN_PUMP_RELAY, OUTPUT);
  digitalWrite(PIN_BUZZER, BUZZER_ACTIVE_HIGH ? LOW : HIGH);
  pinMode(PIN_BUZZER, OUTPUT);
  pinMode(PIN_LEVEL_LOW, INPUT_PULLUP);
  pinMode(PIN_LEVEL_MED, INPUT_PULLUP);
  pinMode(PIN_LEVEL_HIGH, INPUT_PULLUP);

  analogReadResolution(12);
  analogSetPinAttenuation(PIN_PH, ADC_11db);
  analogSetPinAttenuation(PIN_TDS, ADC_11db);
  analogSetPinAttenuation(PIN_TURBIDITY, ADC_11db);
  analogSetPinAttenuation(PIN_BATTERY, ADC_11db);
  pinMode(PIN_FLOW, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(PIN_FLOW), countFlowPulse, FALLING);
  lastFlowMeasurementMs = millis();
  updateWaterControl();
  xTaskCreatePinnedToCore(
    waterControlTask, "water-control", 2048, nullptr, 2, nullptr, 1
  );
  Serial.println("\nIP Aqua Tech - Water Quality and Tank Controller");
  Serial.println("GPIO34 pH | GPIO35 TDS | GPIO32 Turbidity | GPIO33 Battery | GPIO27 Flow");
  Serial.println("Level: GPIO18 Low | GPIO19 Medium | GPIO21 High");
  Serial.println("Shared level/LED: GPIO18 Low | GPIO19 Medium | GPIO21 High");
  Serial.println("Output: GPIO26 TIP122/Relay | GPIO22 Buzzer");
  connectWiFi();
  lastSendMs = millis() - SEND_INTERVAL_MS;
  lastThresholdSyncMs = 0;
}

void loop() {
  // The independent task keeps level, schedule, and runtime protection responsive.
  maintainWiFi();
  if (WiFi.status() != WL_CONNECTED) {
    delay(50);
    return;
  }
  if (lastThresholdSyncMs == 0
      || millis() - lastThresholdSyncMs >= THRESHOLD_SYNC_INTERVAL_MS) {
    lastThresholdSyncMs = millis();
    loadThresholdsFromFirebase();
  }
  if (millis() - lastSendMs < SEND_INTERVAL_MS) {
    delay(50);
    return;
  }
  lastSendMs = millis();

  SensorReading reading = readSensors();
  Serial.printf(
    "Flow=%.2fL/min | pH=%.2f (%.3fV) | TDS=%.0fppm (%.3fV) | Turbidity=%.2fNTU (%.3fV)\n",
    reading.flowRate, reading.ph, reading.rawPhVoltage,
    reading.tds, reading.rawTdsVoltage,
    reading.turbidity, reading.rawTurbidityVoltage
  );
  Serial.printf(
    "Level=%s (%d%%) | Pump=%s | Dirty=%s | LevelFault=%s\n",
    reading.waterLevelStatus.c_str(), reading.waterLevelPercent,
    reading.pumpOn ? "ON" : "OFF",
    reading.dirtyWater ? "YES" : "NO",
    reading.levelSensorFault ? "YES" : "NO"
  );
  Serial.printf(
    "Warning=%s | Battery=%.2fV %.0f%% (%s) | System=%s\n",
    reading.warningLevel.c_str(), reading.batteryVoltage,
    reading.batteryPercent, reading.batteryStatus.c_str(),
    reading.systemStatus.c_str()
  );
  bool firebaseOk = !SEND_TO_FIREBASE || sendToFirebase(reading);
  Serial.printf("Result: Firebase=%s\n\n",
                firebaseOk ? "OK" : "FAILED");
}
