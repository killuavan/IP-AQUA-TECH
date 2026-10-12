/**
 * IP Aqua Tech – SIMPLE IoT (Stage 1)
 * Sensors only: pH, TDS, Turbidity
 *
 * Board : ESP32
 * Serial: 115200 baud
 *
 * USE_MOCK = true  → fake values (no hardware yet)
 * USE_MOCK = false → read real ADC pins
 */

// =============================================================================
// SETTINGS
// =============================================================================

// Sensors are wired — read real ADC. Set true only for demo without hardware.
const bool USE_MOCK = false;

// Sample every 2 seconds
const unsigned long SAMPLE_MS = 2000;

// ESP32 ADC pins – baguhin kung iba wiring mo
const int PIN_PH        = 34;  // pH sensor analog out
const int PIN_TDS       = 35;  // TDS sensor analog out
const int PIN_TURBIDITY = 32;  // turbidity sensor analog out

// =============================================================================
// HELPERS
// =============================================================================

float clampf(float v, float lo, float hi) {
  if (v < lo) return lo;
  if (v > hi) return hi;
  return v;
}

// ESP32 12-bit ADC → ~0–3.3V
float readVoltage(int pin) {
  int raw = analogRead(pin);
  return (raw / 4095.0f) * 3.3f;
}

// =============================================================================
// SENSORS: pH, TDS, Turbidity
// =============================================================================

float readPH() {
  if (USE_MOCK) {
    return 6.8f + (random(0, 60) / 100.0f);  // ~6.8–7.4
  }
  // Calibrate later with pH 4 / 7 / 10 buffers
  float v = readVoltage(PIN_PH);
  return clampf(7.0f + ((1.65f - v) * 3.5f), 0.0f, 14.0f);
}

float readTDS() {
  if (USE_MOCK) {
    return 100.0f + random(0, 100);  // ppm
  }
  // Replace with your TDS module formula after calibration
  float v = readVoltage(PIN_TDS);
  return clampf(v * 500.0f, 0.0f, 2000.0f);
}

float readTurbidity() {
  if (USE_MOCK) {
    return 0.2f + (random(0, 50) / 100.0f);  // NTU-ish
  }
  // Check your module: some modules lower voltage = dirtier water
  float v = readVoltage(PIN_TURBIDITY);
  return clampf((3.3f - v) * 1.5f, 0.0f, 10.0f);
}

// Status based on the 3 sensors only
const char* waterStatus(float ph, float tds, float turbidity) {
  if (ph < 6.5f || ph > 8.5f || tds > 500.0f || turbidity > 5.0f) {
    return "CRITICAL";
  }
  if (ph < 6.8f || ph > 8.0f || tds > 300.0f || turbidity > 1.0f) {
    return "WARNING";
  }
  return "NORMAL";
}

// =============================================================================
// MAIN
// =============================================================================

unsigned long lastSample = 0;

void setup() {
  Serial.begin(115200);
  delay(800);

  analogReadResolution(12);
  // Better ADC range on ESP32 (approx 0–3.3V)
  analogSetPinAttenuation(PIN_PH, ADC_11db);
  analogSetPinAttenuation(PIN_TDS, ADC_11db);
  analogSetPinAttenuation(PIN_TURBIDITY, ADC_11db);

  randomSeed(analogRead(0));

  Serial.println();
  Serial.println("====================================");
  Serial.println(" IP Aqua Tech – pH / TDS / Turbidity");
  Serial.println(" REAL sensors (USE_MOCK = false)");
  Serial.println(" Pins: pH=34  TDS=35  Turb=32");
  Serial.println("====================================");
  Serial.println("pH    | TDS    | Turb   | Status   | rawV pH/TDS/Turb");
  Serial.println("-------------------------------------------------------");
}

void loop() {
  if (millis() - lastSample < SAMPLE_MS) {
    return;
  }
  lastSample = millis();

  float vPh   = readVoltage(PIN_PH);
  float vTds  = readVoltage(PIN_TDS);
  float vTurb = readVoltage(PIN_TURBIDITY);

  float ph   = readPH();
  float tds  = readTDS();
  float turb = readTurbidity();
  const char* status = waterStatus(ph, tds, turb);

  // Values + raw volts (check wiring: volts should move when probe is in water)
  Serial.printf(
    "%.2f  | %6.0f | %6.2f | %-8s | %.2f / %.2f / %.2f V\n",
    ph, tds, turb, status, vPh, vTds, vTurb
  );
}
