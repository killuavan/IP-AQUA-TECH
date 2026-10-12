"""
Rain + turbid spring water (malabo na bukal) prediction engine.

- Rules: always available baseline score
- ML (scikit-learn RandomForest): used when model is trained
- Hybrid: ML probability + rules score combined when both exist
"""
from __future__ import annotations

from typing import Any, Optional

from django.conf import settings
from django.utils import timezone

from monitoring.models import WaterQuality, get_monitoring_thresholds

from .ml_engine import is_model_trained, load_meta, predict_malabo
from .models import MonthlyRainPrediction, RiskLevel, TurbidityRiskPrediction, WeatherSnapshot
from .monthly_rain import (
    is_cloud_model_trained,
    is_monthly_model_trained,
    load_cloud_meta,
    load_monthly_meta,
    predict_monthly_rain,
    train_monthly_rain_model,
    train_spring_cloud_model,
)
from .weather_client import fetch_weather


def get_latest_water_quality() -> Optional[WaterQuality]:
    return WaterQuality.objects.order_by('-recorded_at').first()


def save_weather_snapshot(force_stub: bool = False) -> WeatherSnapshot:
    data = fetch_weather(force_stub=force_stub)
    return WeatherSnapshot.objects.create(
        source=data.get('source', 'stub'),
        location_name=data.get('location_name', ''),
        latitude=data['latitude'],
        longitude=data['longitude'],
        rain_last_1h_mm=data.get('rain_last_1h_mm', 0.0),
        rain_last_24h_mm=data.get('rain_last_24h_mm', 0.0),
        rain_next_24h_mm=data.get('rain_next_24h_mm', 0.0),
        rain_probability_max_pct=data.get('rain_probability_max_pct', 0.0),
        will_rain_next_24h=data.get('will_rain_next_24h', False),
        humidity_pct=data.get('humidity_pct'),
        cloud_cover_pct=data.get('cloud_cover_pct'),
        temperature_c=data.get('temperature_c'),
        raw_payload=data.get('raw_payload') or {},
    )


def _thresholds() -> dict:
    wq = get_monitoring_thresholds()
    turb = wq.get('turbidity', {})
    return {
        'turb_warning': float(turb.get('max_normal', 1.0)),
        'turb_critical': float(turb.get('max_warning', 5.0)),
        'rain_past_medium': float(getattr(settings, 'PREDICTION_RAIN_PAST_MEDIUM_MM', 5.0)),
        'rain_past_high': float(getattr(settings, 'PREDICTION_RAIN_PAST_HIGH_MM', 15.0)),
        'rain_next_medium': float(getattr(settings, 'PREDICTION_RAIN_NEXT_MEDIUM_MM', 3.0)),
        'rain_next_high': float(getattr(settings, 'PREDICTION_RAIN_NEXT_HIGH_MM', 10.0)),
        'malabo_score': float(getattr(settings, 'PREDICTION_MALABO_SCORE_THRESHOLD', 45.0)),
    }


def score_turbidity_risk(
    *,
    rain_last_24h_mm: float,
    rain_next_24h_mm: float,
    rain_probability_pct: float,
    will_rain: bool,
    turbidity: Optional[float],
    tds: Optional[float],
    ph: Optional[float],
) -> dict[str, Any]:
    """
    Rule-based composite score 0–100 for malabo na bukal risk.

    Heavy weight on:
      - recent rain (runoff already happening)
      - forecast rain (risk rising)
      - current turbidity (already cloudy)
    """
    th = _thresholds()
    score = 0.0
    reasons: list[str] = []
    recommendations: list[str] = []

    # --- Rain past 24h (0–35) ---
    if rain_last_24h_mm >= th['rain_past_high']:
        score += 35
        reasons.append(f'Heavy rain in the last 24h ({rain_last_24h_mm:.1f} mm).')
    elif rain_last_24h_mm >= th['rain_past_medium']:
        score += 22
        reasons.append(f'Rain in the last 24h ({rain_last_24h_mm:.1f} mm).')
    elif rain_last_24h_mm >= 1.0:
        score += 10
        reasons.append(f'Light rain recently ({rain_last_24h_mm:.1f} mm).')

    # --- Rain next 24h (0–30) ---
    if rain_next_24h_mm >= th['rain_next_high']:
        score += 30
        reasons.append(f'Heavy rain expected next 24h ({rain_next_24h_mm:.1f} mm).')
    elif rain_next_24h_mm >= th['rain_next_medium'] or (will_rain and rain_probability_pct >= 60):
        score += 18
        reasons.append(
            f'Rain expected next 24h ({rain_next_24h_mm:.1f} mm, ~{rain_probability_pct:.0f}% chance).'
        )
    elif will_rain or rain_probability_pct >= 40:
        score += 8
        reasons.append(f'Possible rain (~{rain_probability_pct:.0f}% probability).')

    # --- Current turbidity (0–30) ---
    if turbidity is not None:
        if turbidity >= th['turb_critical']:
            score += 30
            reasons.append(f'Turbidity already high ({turbidity:.2f} NTU) – water is cloudy.')
        elif turbidity >= th['turb_warning']:
            score += 18
            reasons.append(f'Turbidity elevated ({turbidity:.2f} NTU).')
        elif turbidity >= th['turb_warning'] * 0.5:
            score += 8
            reasons.append(f'Turbidity slightly up ({turbidity:.2f} NTU).')
        else:
            reasons.append(f'Turbidity OK for now ({turbidity:.2f} NTU).')
    else:
        reasons.append('No latest turbidity reading – using rain features only.')
        score += 5  # slight uncertainty

    # --- TDS support (0–5) ---
    tds_warn = float(get_monitoring_thresholds().get('tds', {}).get('max_normal', 300))
    if tds is not None and tds > tds_warn:
        score += 5
        reasons.append(f'TDS elevated ({tds:.0f} ppm) – possible runoff influence.')

    score = max(0.0, min(100.0, score))

    if score >= 75:
        risk = RiskLevel.CRITICAL
    elif score >= 55:
        risk = RiskLevel.HIGH
    elif score >= 35:
        risk = RiskLevel.MEDIUM
    else:
        risk = RiskLevel.LOW

    predicted_malabo = score >= th['malabo_score']

    # Recommendations
    if predicted_malabo or risk in (RiskLevel.HIGH, RiskLevel.CRITICAL):
        recommendations.append('Prepare pre-filter / sediment filter before load increases.')
        recommendations.append('Monitor turbidity more often (every 1–2 hours).')
        recommendations.append('Avoid high production if the source is very cloudy.')
    elif risk == RiskLevel.MEDIUM:
        recommendations.append('Watch rain and turbidity; be ready for a filter check.')
    else:
        recommendations.append('Normal operations; continue regular monitoring.')

    if will_rain:
        recommendations.append('Rain forecast – spring runoff possible after rain starts.')

    if not reasons:
        reasons.append('No significant rain or turbidity signal.')

    summary = (
        f'Risk {risk}: possible cloudy spring water'
        if predicted_malabo
        else f'Risk {risk}: spring water likely clear for now'
    )

    return {
        'risk_level': risk,
        'turbidity_risk_score': round(score, 1),
        'predicted_malabo': predicted_malabo,
        'method': 'rules',
        'summary': summary,
        'reasons': reasons,
        'recommendations': recommendations,
        'details': {
            'thresholds': th,
            'inputs': {
                'rain_last_24h_mm': rain_last_24h_mm,
                'rain_next_24h_mm': rain_next_24h_mm,
                'rain_probability_pct': rain_probability_pct,
                'will_rain': will_rain,
                'turbidity': turbidity,
                'tds': tds,
                'ph': ph,
            },
        },
    }


def _risk_from_score(score: float) -> str:
    if score >= 75:
        return RiskLevel.CRITICAL
    if score >= 55:
        return RiskLevel.HIGH
    if score >= 35:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def run_prediction(
    *,
    user=None,
    force_stub_weather: bool = False,
    weather: Optional[WeatherSnapshot] = None,
    use_ml: bool = True,
) -> TurbidityRiskPrediction:
    """Fetch weather, read latest WQ, score with rules + optional ML, save."""
    if weather is None:
        weather = save_weather_snapshot(force_stub=force_stub_weather)

    wq = get_latest_water_quality()
    ph = float(wq.ph) if wq else None
    tds = float(wq.tds) if wq else None
    turbidity = float(wq.turbidity) if wq else None

    result = score_turbidity_risk(
        rain_last_24h_mm=weather.rain_last_24h_mm,
        rain_next_24h_mm=weather.rain_next_24h_mm,
        rain_probability_pct=weather.rain_probability_max_pct,
        will_rain=weather.will_rain_next_24h,
        turbidity=turbidity,
        tds=tds,
        ph=ph,
    )

    ml_out = None
    if use_ml and is_model_trained():
        features = {
            'rain_last_24h_mm': weather.rain_last_24h_mm,
            'rain_next_24h_mm': weather.rain_next_24h_mm,
            'rain_probability_pct': weather.rain_probability_max_pct,
            'humidity_pct': weather.humidity_pct,
            'cloud_cover_pct': weather.cloud_cover_pct,
            'turbidity': turbidity,
            'tds': tds,
            'ph': ph,
        }
        ml_out = predict_malabo(features)

    if ml_out:
        # Hybrid score: blend rules score with ML probability
        ml_score = float(ml_out['probability_malabo'])
        rules_score = float(result['turbidity_risk_score'])
        hybrid = round(0.55 * ml_score + 0.45 * rules_score, 1)
        predicted = ml_out['predicted_malabo'] or hybrid >= float(
            getattr(settings, 'PREDICTION_MALABO_SCORE_THRESHOLD', 45)
        )
        risk = _risk_from_score(hybrid)
        result['turbidity_risk_score'] = hybrid
        result['predicted_malabo'] = predicted
        result['risk_level'] = risk
        result['method'] = 'hybrid_ml'
        result['summary'] = (
            f'ML+Rules {risk}: possible cloudy spring water '
            f'(ML prob {ml_out["probability_malabo"]}%)'
            if predicted
            else f'ML+Rules {risk}: spring likely clear '
            f'(ML prob {ml_out["probability_malabo"]}%)'
        )
        result['reasons'] = [
            f'ML (RandomForest) probability of cloudy spring: {ml_out["probability_malabo"]}%.',
            f'Model train accuracy: {ml_out.get("model_accuracy", "n/a")} '
            f'on {ml_out.get("n_samples_trained", "?")} samples.',
        ] + list(result['reasons'])
        result['details'] = {
            **result.get('details', {}),
            'ml': ml_out,
            'hybrid_weights': {'ml': 0.55, 'rules': 0.45},
        }

    day = next_day_target()
    # Prefix summary as day forecast (tomorrow only)
    day_prefix = f'Day forecast ({day["day_label"]}): '
    summary = day_prefix + str(result['summary'])
    details = {
        **(result.get('details') or {}),
        'forecast_scope': 'next_day_only',
        'target_day': day['iso'],
        'target_day_label': day['day_label'],
        'weekday': day['weekday'],
    }

    return TurbidityRiskPrediction.objects.create(
        weather=weather,
        ph=ph,
        tds=tds,
        turbidity=turbidity,
        rain_last_24h_mm=weather.rain_last_24h_mm,
        rain_next_24h_mm=weather.rain_next_24h_mm,
        rain_probability_pct=weather.rain_probability_max_pct,
        will_rain=weather.will_rain_next_24h,
        risk_level=result['risk_level'],
        turbidity_risk_score=result['turbidity_risk_score'],
        predicted_malabo=result['predicted_malabo'],
        method=result['method'],
        summary=summary,
        reasons=result['reasons'],
        recommendations=result['recommendations'],
        details=details,
        created_by=user if getattr(user, 'is_authenticated', False) else None,
    )


def next_month_target(ref=None) -> dict[str, Any]:
    """
    Only the next calendar month may be predicted.
    Example: if today is July 2026 → August 2026 only.
    """
    from calendar import month_name
    from dateutil.relativedelta import relativedelta

    if ref is None:
        ref = timezone.localtime().date()
    elif hasattr(ref, 'date'):
        ref = ref.date()
    nxt = ref + relativedelta(months=1)
    return {
        'year': nxt.year,
        'month': nxt.month,
        'month_label': f'{month_name[nxt.month]} {nxt.year}',
        'current_year': ref.year,
        'current_month': ref.month,
        'current_month_label': f'{month_name[ref.month]} {ref.year}',
    }


def next_day_target(ref=None) -> dict[str, Any]:
    """
    Only the next calendar day may be predicted (day forecast).
    Example: if today is 23 Jul 2026 → 24 Jul 2026 only.
    """
    from datetime import timedelta

    if ref is None:
        now = timezone.localtime()
        ref = now.date()
    elif hasattr(ref, 'date'):
        ref = ref.date()
    nxt = ref + timedelta(days=1)
    return {
        'date': nxt,
        'day_label': nxt.strftime('%B %d, %Y'),
        'weekday': nxt.strftime('%A'),
        'iso': nxt.isoformat(),
        'current_date': ref,
        'current_day_label': ref.strftime('%B %d, %Y'),
    }


def ensure_auto_monthly_prediction(user=None) -> Optional[MonthlyRainPrediction]:
    """
    Auto-predict next month once per calendar day.

    If a prediction for the target next month was already created today,
    do nothing. Otherwise run ML and save a new MonthlyRainPrediction.
    """
    if not getattr(settings, 'PREDICTION_AUTO_MONTHLY', True):
        return None

    target = next_month_target()
    today = timezone.localtime().date()
    already_today = MonthlyRainPrediction.objects.filter(
        year=target['year'],
        month=target['month'],
        created_at__date=today,
    ).exists()
    if already_today:
        return None

    # Need at least the monthly rain model for a meaningful auto run
    if not is_monthly_model_trained():
        return None

    return run_monthly_rain_prediction(
        user=user,
        force_next_month_only=True,
        auto=True,
    )


def run_monthly_rain_prediction(
    *,
    year: Optional[int] = None,
    month: Optional[int] = None,
    user=None,
    force_next_month_only: bool = True,
    auto: bool = False,
) -> MonthlyRainPrediction:
    """
    Predict rainfall for one month and save.

    By default only the *next* calendar month is allowed
    (e.g. July now → predict August only).
    """
    target = next_month_target()
    if force_next_month_only:
        year = target['year']
        month = target['month']
    else:
        year = int(year or target['year'])
        month = int(month or target['month'])

    result = predict_monthly_rain(year, month)
    return MonthlyRainPrediction.objects.create(
        year=result['year'],
        month=result['month'],
        location_name=result['location_name'],
        latitude=result['latitude'],
        longitude=result['longitude'],
        climate_normal_mm=result['climate_normal_mm'],
        predicted_total_mm=result['predicted_total_mm'],
        predicted_rainy_days=result['predicted_rainy_days'],
        rain_level=result['rain_level'],
        will_be_rainy_month=result['will_be_rainy_month'],
        spring_dirt_probability_pct=result.get('spring_dirt_probability_pct', 0.0),
        spring_dirt_risk_level=result.get('spring_dirt_risk_level', 'LOW'),
        predicted_dirty_spring=result.get('predicted_dirty_spring', False),
        dirt_reasons=result.get('dirt_reasons') or [],
        method=result['method'],
        summary=result['summary'],
        recommendations=result['recommendations'],
        level_probabilities=result['level_probabilities_pct'],
        details={
            'climate_info': result['climate_info'],
            'features': result['features'],
            'dirt_method': result.get('dirt_method'),
            'cloud_model_accuracy': result.get('cloud_model_accuracy'),
            'auto': bool(auto),
            'trigger': 'auto' if auto else 'manual',
        },
        created_by=user if getattr(user, 'is_authenticated', False) else None,
    )


def train_all_ml_models() -> dict[str, Any]:
    """Train malabo + monthly rain + spring cloud (lalabo) ML models."""
    from .ml_engine import train_model
    malabo = train_model(n_synthetic=2000, use_real=True)
    monthly = train_monthly_rain_model(n_per_month=80)
    # cloud model also trained inside train_monthly_rain_model; ensure present
    cloud = monthly.get('spring_cloud') or train_spring_cloud_model()
    return {
        'malabo': malabo,
        'monthly_rain': monthly,
        'spring_cloud': cloud,
    }


def dashboard_context() -> dict[str, Any]:
    from calendar import month_name

    latest = TurbidityRiskPrediction.objects.select_related('weather').first()
    recent = TurbidityRiskPrediction.objects.select_related('weather')[:12]
    weather = WeatherSnapshot.objects.first()
    wq = get_latest_water_quality()
    latest_monthly = MonthlyRainPrediction.objects.first()
    recent_monthly = MonthlyRainPrediction.objects.all()[:8]
    loc = {
        'name': getattr(settings, 'PREDICTION_LOCATION_NAME', 'Philippines'),
        'lat': getattr(settings, 'PREDICTION_LATITUDE', 14.5995),
        'lon': getattr(settings, 'PREDICTION_LONGITUDE', 120.9842),
    }
    from .ml_engine import dataset_csv_path, meta_path, model_path
    from .monthly_rain import (
        cloud_dataset_path,
        cloud_meta_path,
        cloud_model_path,
        monthly_dataset_path,
        monthly_meta_path,
        monthly_model_path,
    )

    ml_meta = load_meta() if is_model_trained() else {}
    monthly_meta = load_monthly_meta() if is_monthly_model_trained() else {}
    cloud_meta = load_cloud_meta() if is_cloud_model_trained() else {}
    now = timezone.localtime()
    # (number, label) for select dropdowns
    month_choices = [(m, month_name[m]) for m in range(1, 13)]

    def _sorted_importances(meta: dict, key: str = 'feature_importances', top: int = 5):
        imp = meta.get(key) or {}
        if not isinstance(imp, dict):
            return []
        items = sorted(imp.items(), key=lambda x: float(x[1]), reverse=True)
        return [(name, round(float(v) * 100, 1)) for name, v in items[:top]]

    ml_cards = [
        {
            'title': 'Monthly rainfall',
            'ready': is_monthly_model_trained(),
            'algorithm': monthly_meta.get('algorithm', 'RandomForest'),
            'target': 'DRY / MODERATE / WET + mm + rainy days',
            'n_samples': monthly_meta.get('n_samples', 0),
            'dataset_type': monthly_meta.get(
                'dataset',
                'synthetic PH seasonal climate normals + noise',
            ),
            'metrics': [
                ('Level accuracy', f"{(monthly_meta.get('accuracy_level') or 0) * 100:.1f}%"),
                ('MAE mm', f"{monthly_meta.get('mae_total_mm', '—')}"),
                ('MAE days', f"{monthly_meta.get('mae_rainy_days', '—')}"),
            ] if monthly_meta else [],
            'model_file': monthly_model_path().name if is_monthly_model_trained() else '—',
            'dataset_file': monthly_dataset_path().name if monthly_dataset_path().exists() else '—',
            'meta_file': monthly_meta_path().name if monthly_meta_path().exists() else '—',
            'importances': [],
            'badge': 'primary',
            'show_on_dashboard': True,
        },
        {
            'title': 'Cloudy chance when it rains',
            'ready': is_cloud_model_trained(),
            'algorithm': cloud_meta.get('algorithm', 'RandomForestClassifier'),
            'target': 'Chance (%) spring water becomes cloudy when it rains',
            'n_samples': cloud_meta.get('n_samples', 0),
            'dataset_type': cloud_meta.get(
                'dataset',
                'synthetic rain-to-cloudy (more rain → higher cloudy chance)',
            ),
            'metrics': [
                ('Accuracy', f"{(cloud_meta.get('accuracy') or 0) * 100:.1f}%"),
                ('F1', f"{cloud_meta.get('f1', '—')}"),
                ('ROC-AUC', f"{cloud_meta.get('roc_auc', '—')}"),
            ] if cloud_meta else [],
            'model_file': cloud_model_path().name if is_cloud_model_trained() else '—',
            'dataset_file': cloud_dataset_path().name if cloud_dataset_path().exists() else '—',
            'meta_file': cloud_meta_path().name if cloud_meta_path().exists() else '—',
            'importances': _sorted_importances(cloud_meta),
            'badge': 'danger',
            'show_on_dashboard': True,
        },
    ]

    return {
        'latest_prediction': latest,
        'recent_predictions': recent,
        'latest_weather': weather,
        'latest_water_quality': wq,
        'latest_monthly': latest_monthly,
        'recent_monthly': recent_monthly,
        'location': loc,
        'stub_mode': getattr(settings, 'PREDICTION_WEATHER_STUB', False),
        'now': timezone.now(),
        'current_year': now.year,
        'current_month': now.month,
        'ml_trained': is_model_trained(),
        'ml_meta': ml_meta,
        'monthly_ml_trained': is_monthly_model_trained(),
        'monthly_ml_meta': monthly_meta,
        'cloud_ml_trained': is_cloud_model_trained(),
        'cloud_ml_meta': cloud_meta,
        'ml_cards': ml_cards,
        'ml_folder': 'predictions/ml_models/',
        'month_choices': month_choices,
        'year_choices': list(range(now.year - 1, now.year + 3)),
        # Only next month can be predicted
        'predict_target': next_month_target(now),
        'day_target': next_day_target(now),
        'auto_predict_enabled': getattr(settings, 'PREDICTION_AUTO_MONTHLY', True),
    }
