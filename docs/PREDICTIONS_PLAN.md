# IP Aqua Tech – Rain & Malabo na Bukal Predictions

## Goal

Predict:

1. **Ulan sa buwan** (primary) – DRY / MODERATE / WET for a whole calendar month + estimated mm & rainy days (ML)  
2. **Chance na lalabo ang tubig sa bukal pag umulan** – **real ML** (RandomForest `predict_proba`) on monthly rain features → % chance spring becomes cloudy  
3. **Ulan short-term** (optional) – next ~24h via Open-Meteo  
4. **Malabo short-term** (optional) – turbid spring risk using 24h rain + live sensors

## Why this fits the capstone

After rain / runoff, spring sources often become **cloudy (malabo)**.  
Early warning helps operators prepare **pre-filters**, reduce production load, and check maintenance.  
Monthly rain forecast helps plan filtration load for the whole season.

## Architecture

```
Open-Meteo climate archive  ──►  climate_normal_mm
        │
        ▼
 Monthly Rain ML (RandomForest)
  → DRY / MODERATE / WET + mm + rainy days
        │
        ▼
  MonthlyRainPrediction  →  UI /predictions/

Open-Meteo forecast  ──►  WeatherSnapshot
ESP32 / Manual       ──►  WaterQuality (pH, TDS, turbidity)
        │
        ▼
 Rules + Malabo ML (RandomForest hybrid)
        │
        ▼
  TurbidityRiskPrediction  →  UI /predictions/
```

## Phase 1 – Rules (implemented)

| Piece | Status |
|-------|--------|
| Django app `predictions` | Done |
| Open-Meteo weather client + offline stub | Done |
| Rule-based risk score 0–100 | Done |
| Dashboard + history | Done |
| Admin models | Done |

### Risk scoring (rules) – malabo short-term

| Factor | Weight idea |
|--------|-------------|
| Rain last 24h | up to +35 |
| Rain next 24h / probability | up to +30 |
| Current turbidity | up to +30 |
| Elevated TDS | up to +5 |

- Score ≥ 45 → `predicted_malabo = True` (configurable)  
- Risk bands: LOW / MEDIUM / HIGH / CRITICAL  

## Phase 2 – Machine Learning (implemented)

### A) Monthly rain (primary) – **real ML**

| Piece | Detail |
|-------|--------|
| Algorithm | `RandomForestClassifier` + 2× `RandomForestRegressor` |
| Outputs | rain level (DRY/MODERATE/WET), total mm, rainy days |
| Features | month, month_sin/cos, climate_normal_mm, lat, lon, year_offset |
| Train command | `python manage.py train_monthly_rain` |
| Or UI | Admin → **Train / Retrain ALL ML** on `/predictions/` |
| Model file | `predictions/ml_models/monthly_rain_rf.joblib` |
| Dataset CSV | `predictions/ml_models/monthly_rain_dataset.csv` |
| Metrics JSON | `predictions/ml_models/monthly_rain_rf_meta.json` |
| Inference | Hybrid: 65% ML mm + 35% climate normal; level from hybrid mm |

**Dataset:** synthetic PH seasonal climate normals + noise (default 480 samples = 40/month × 12).  
At predict time, climate normal can come from **Open-Meteo archive** (10-year average) or offline PH table.

### A2) Chance na lalabo pag umulan – **real ML**

| Piece | Detail |
|-------|--------|
| Algorithm | `RandomForestClassifier` + `predict_proba` |
| Output | 0–100% chance spring water becomes cloudy (lalabo) when it rains |
| Features | total_mm, rainy_days, rain_level_code, month, month_sin/cos, climate_normal_mm, wet_prob, dry_prob |
| Train | `python manage.py train_monthly_rain` (trains rain + cloud together) |
| Model file | `predictions/ml_models/spring_cloud_rf.joblib` |
| Dataset CSV | `predictions/ml_models/spring_cloud_dataset.csv` |
| Metrics JSON | `predictions/ml_models/spring_cloud_rf_meta.json` |
| Inference | Hybrid: 85% ML probability + 15% domain baseline |

**Dataset:** 900 synthetic rain→runoff→lalabo samples (domain-informed). More rain / rainy days → higher P(lalabo).

### B) Malabo na bukal (optional) – **real ML**

| Piece | Detail |
|-------|--------|
| Algorithm | `RandomForestClassifier` |
| Features | rain_last_24h, rain_next_24h, rain_prob, humidity, cloud, turbidity, tds, ph |
| Label | `malabo` 0/1 (turbid spring risk) |
| Train command | `python manage.py train_malabo_model` |
| Model file | `predictions/ml_models/malabo_rf.joblib` |
| Dataset CSV | `predictions/ml_models/training_dataset.csv` |
| Inference | Hybrid: 55% ML probability + 45% rules score |

| Part | What | Typical size |
|------|------|--------------|
| **Real** | Rows from `WaterQuality` DB (+ nearest weather) | 0–1000 (grows with use) |
| **Synthetic (domain)** | Generated rain→runoff→turbidity samples | **800** default |

**Thesis note:** Synthetic data is domain-informed so the project can demo ML before months of field logging. Retrain as real sensor history grows.

### Is the weather API “ML”?

**No.** Open-Meteo only supplies **input features** (forecast / climate normals).  
The **RandomForest** models that map features → rain level / malabo are the ML.

## Phase 3 (optional)

- Auto-run prediction every hour (management command + Task Scheduler)  
- Create `Notification` when HIGH/CRITICAL  
- Chart: rain mm vs turbidity over 7 days  

## Configuration (`settings.py`)

```python
PREDICTION_LOCATION_NAME = 'Your City, Province'
PREDICTION_LATITUDE = 14.5995
PREDICTION_LONGITUDE = 120.9842
PREDICTION_WEATHER_STUB = False  # True = always demo weather
MONTHLY_RAIN_DRY_MAX_MM = 80.0   # below → DRY
MONTHLY_RAIN_WET_MIN_MM = 250.0  # at/above → WET
```

Find lat/lon: [Open-Meteo geocoding](https://open-meteo.com/en/docs) or Google Maps.

## URLs

| URL | Purpose |
|-----|---------|
| `/predictions/` | Dashboard (monthly rain + malabo) |
| `/predictions/run-monthly/` | POST monthly rain prediction |
| `/predictions/run/` | POST short-term malabo prediction |
| `/predictions/train/` | POST retrain both ML models (admin) |
| `/predictions/history/monthly/` | Monthly rain history |
| `/predictions/history/` | Malabo prediction history |
| `/predictions/weather/` | Weather fetch log |

## How to demo (defense)

1. Open **Ulan sa Buwan** in sidebar → `/predictions/`  
2. Pick year/month → **Predict Ulan sa Buwan**  
3. Show DRY/MODERATE/WET card, mm, rainy days, probability bars  
4. (Optional) Train/Retrain ALL ML as admin; show accuracy from meta  
5. (Optional) Run malabo risk with water quality + weather  
6. Explain: *ML RandomForest predicts monthly rain; weather API is input only*

## CLI

```bash
# Train models
python manage.py train_monthly_rain
python manage.py train_malabo_model

# Or both via UI: Train / Retrain ALL ML
```

## Thesis wording

> Ang sistema ay gumagamit ng machine learning (Random Forest) upang hulaan ang antas ng pag-ulan sa isang buwan (DRY / MODERATE / WET) at, opsyonal, ang panganib ng malabong tubig-bukal batay sa weather forecast at real-time turbidity, TDS, at pH, upang maagang makapaghanda ang filtration operations.
