"""Dashboard views – system overview and chart data APIs."""
import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Avg
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from filters.models import Filter
from maintenance.models import Maintenance, MaintenanceStatus
from monitoring.models import (
    WaterQuality, WaterTank, Pump, WaterProduction, StatusChoices,
    get_monitoring_thresholds,
)
from notifications.models import Notification
from solar.models import SolarSystem, Battery, SolarEnergyLog, PowerStatus
from .models import SystemConfig


def _decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError


def _dashboard_datetime(value, default):
    if not value:
        return default
    parsed = parse_datetime(value)
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


@login_required
def index(request):
    # Refresh device state before the overview is rendered.
    from iot.services import mark_stale_devices_offline, pull_latest_from_firebase
    mark_stale_devices_offline()
    try:
        pull_latest_from_firebase()
    except Exception:
        # Keep the dashboard available when Firebase is temporarily offline.
        pass

    now = timezone.now()
    today = now.date()
    chart_from = _dashboard_datetime(
        request.GET.get('from_datetime'), now - timedelta(days=14),
    )
    chart_to = _dashboard_datetime(request.GET.get('to_datetime'), now)
    if chart_from is None or chart_to is None or chart_from > chart_to:
        chart_from = now - timedelta(days=14)
        chart_to = now
    latest_wq = WaterQuality.objects.filter(recorded_at__lte=now).first()
    selected_wq = WaterQuality.objects.filter(
        recorded_at__gte=chart_from,
        recorded_at__lte=min(chart_to, now),
    ).first()
    latest_solar = SolarSystem.objects.first()
    battery = Battery.objects.first()
    tank = WaterTank.objects.first()
    pump = Pump.objects.first()
    filters = Filter.objects.filter(is_active=True)
    filter_alert = filters.filter(life_percentage__lte=25).exists()

    production_today = WaterProduction.objects.filter(date=today).first()
    day_prod = float(production_today.daily_production_liters) if production_today else 0.0
    week_start = today - timedelta(days=today.weekday())
    week_prod = float(
        WaterProduction.objects.filter(
            date__gte=week_start, date__lte=today
        ).aggregate(total=Sum('daily_production_liters'))['total'] or 0
    )

    month_prod = float(
        WaterProduction.objects.filter(
            date__year=today.year, date__month=today.month
        ).aggregate(total=Sum('daily_production_liters'))['total'] or 0
    )

    total_prod = float(
        WaterProduction.objects.aggregate(
            total=Sum('daily_production_liters')
        )['total'] or 0
    )

    # LOW / MID / HIGH from today's sensor production only (not week/month/total)
    from django.conf import settings as dj_settings
    bands = getattr(dj_settings, 'PRODUCTION_LEVELS', {}).get('daily', {})
    mid = float(bands.get('mid', 500))
    high = float(bands.get('high', 1500))
    # Prefer today's WaterProduction (from flow sensor / IoT); fallback latest flow_rate estimate
    sensor_liters = day_prod
    if sensor_liters <= 0 and latest_wq and latest_wq.flow_rate is not None:
        # rough daily estimate from current flow (L/min) × 60 × operating hours factor
        sensor_liters = float(latest_wq.flow_rate) * 60.0 * 8.0  # 8h operating day estimate
    if sensor_liters >= high:
        day_level = 'HIGH'
    elif sensor_liters >= mid:
        day_level = 'MID'
    else:
        day_level = 'LOW'

    active_alerts = Notification.objects.filter(is_resolved=False)[:10]
    alert_count = Notification.objects.filter(is_resolved=False).count()

    pending_maintenance = Maintenance.objects.exclude(
        status__in=[MaintenanceStatus.COMPLETED, MaintenanceStatus.CANCELLED]
    ).count()

    system = SystemConfig.objects.filter(is_active=True).first()

    # Live weather via Open-Meteo (free API, no key). Never show demo values here.
    weather = None
    weather_error = None
    try:
        from predictions.weather_client import fetch_weather
        weather = fetch_weather(
            force_stub=False,
            allow_fallback=False,
            allow_stub_setting=False,
        )
    except Exception as exc:
        weather_error = str(exc)

    # Determine overall system status
    overall = 'OPERATIONAL'
    if (
        (latest_wq and latest_wq.status == StatusChoices.CRITICAL)
        or (battery and battery.status == PowerStatus.CRITICAL)
        or (pump and pump.pump_status == 'MALFUNCTION')
    ):
        overall = 'CRITICAL'
    elif (
        (latest_wq and latest_wq.status == StatusChoices.WARNING)
        or (battery and battery.status == PowerStatus.WARNING)
        or filter_alert
    ):
        overall = 'DEGRADED'

    context = {
        'system': system,
        'overall_status': overall,
        'latest_wq': latest_wq,
        'selected_wq': selected_wq,
        'latest_solar': latest_solar,
        'battery': battery,
        'tank': tank,
        'pump': pump,
        'filters': filters[:5],
        'filter_alert': filter_alert,
        'production_today': production_today,
        'day_prod': day_prod,
        'week_prod': week_prod,
        'month_prod': month_prod,
        'total_prod': total_prod,
        'day_level': day_level,
        'production_mid': mid,
        'production_high': high,
        'sensor_liters_used': sensor_liters,
        'active_alerts': active_alerts,
        'alert_count': alert_count,
        'pending_maintenance': pending_maintenance,
        'weather': weather,
        'weather_error': weather_error,
        'monitoring_thresholds': get_monitoring_thresholds(),
        'chart_from': timezone.localtime(chart_from).strftime('%Y-%m-%dT%H:%M'),
        'chart_to': timezone.localtime(chart_to).strftime('%Y-%m-%dT%H:%M'),
        'chart_from_iso': timezone.localtime(chart_from).isoformat(),
        'chart_to_iso': timezone.localtime(chart_to).isoformat(),
    }
    return render(request, 'dashboard/index.html', context)


@login_required
def chart_data(request):
    """JSON API for Chart.js dashboard graphs."""
    now = timezone.now()
    today = now.date()
    range_start = now - timedelta(days=14)
    range_start = _dashboard_datetime(request.GET.get('from_datetime'), range_start)
    range_end = _dashboard_datetime(request.GET.get('to_datetime'), now)
    if range_start is None or range_end is None or range_start > range_end:
        return JsonResponse({'error': 'Enter a valid date-time range.'}, status=400)
    range_end = min(range_end, now)
    start = range_start.date()

    # Water production
    prod_qs = WaterProduction.objects.filter(date__gte=start, date__lte=today).order_by('date')
    prod_labels = [p.date.strftime('%b %d') for p in prod_qs]
    prod_data = [float(p.daily_production_liters) for p in prod_qs]

    # Solar energy
    solar_qs = SolarEnergyLog.objects.filter(date__gte=start, date__lte=today).order_by('date')
    solar_labels = [s.date.strftime('%b %d') for s in solar_qs]
    solar_data = [float(s.energy_generated_kwh) for s in solar_qs]

    # Battery – use recent solar readings timestamps if we had history;
    # for demo use latest battery + fill from recent solar timestamps as proxy labels
    battery = Battery.objects.first()
    battery_pct = float(battery.percentage) if battery else 0
    # Build simple series from last N battery-related solar records (power as proxy)
    # Better: store battery snapshots; for now generate labels for last readings
    recent_solar = SolarSystem.objects.filter(
        recorded_at__date__gte=start
    ).filter(recorded_at__lte=range_end).order_by('recorded_at')[:14]
    battery_labels = [r.recorded_at.strftime('%b %d %H:%M') for r in recent_solar] or ['Current']
    # Without historical battery, show current level repeated for chart presence
    # Prefer actual if we expand later
    battery_data = [battery_pct] * len(battery_labels) if battery_labels else [battery_pct]

    # Water quality history
    wq_qs = WaterQuality.objects.filter(
        recorded_at__gte=range_start,
        recorded_at__lte=range_end,
    ).order_by('recorded_at')
    chart_readings = list(wq_qs[:500])
    table_readings = list(wq_qs.order_by('-recorded_at')[:100])
    wq_labels = [timezone.localtime(w.recorded_at).strftime('%b %d %H:%M') for w in chart_readings]
    wq_ph = [float(w.ph) for w in chart_readings]
    wq_tds = [float(w.tds) for w in chart_readings]
    wq_turb = [float(w.turbidity) for w in chart_readings]
    wq_temp = [float(w.temperature) for w in chart_readings]

    return JsonResponse({
        'production': {'labels': prod_labels, 'data': prod_data},
        'solar': {'labels': solar_labels, 'data': solar_data},
        'battery': {'labels': battery_labels, 'data': battery_data, 'current': battery_pct},
        'water_quality': {
            'labels': wq_labels,
            'ph': wq_ph,
            'tds': wq_tds,
            'turbidity': wq_turb,
            'temperature': wq_temp,
            'records': [{
                'recorded_at': timezone.localtime(w.recorded_at).strftime('%b %d, %Y %H:%M'),
                'ph': float(w.ph),
                'tds': float(w.tds),
                'turbidity': float(w.turbidity),
                'temperature': float(w.temperature),
                'status': w.get_status_display(),
            } for w in table_readings],
            'count': wq_qs.count(),
        },
    })
