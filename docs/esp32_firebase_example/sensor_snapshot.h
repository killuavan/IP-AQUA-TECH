#pragma once
#include <Arduino.h>

// Put custom types in a .h so Arduino IDE auto-prototypes can see them.
struct SensorSnapshot {
  float ph, tds, turbidity, temperature, flow_rate, water_pressure, water_level;
  float panel_voltage, panel_current, power_output, power_consumption, irradiance;
  float batt_voltage, batt_pct, batt_temp;
  float tank_level, tank_capacity;
  float system_pressure, pump_power;
  const char* charging;
  const char* pump_status;
  const char* uv_status;
  const char* flow_status;
  String timestamp;
};
