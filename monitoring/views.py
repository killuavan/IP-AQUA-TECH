"""Water quality, tank, pump, and production views."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from datetime import timedelta

from notifications.models import Notification, AlertType, AlertSeverity
from .forms import (
    MonitoringThresholdForm, PumpForm, WaterProductionForm,
    WaterQualityForm, WaterTankForm,
)
from .models import (
    MonitoringThreshold, Pump, WarningLevel,
    WaterProduction, WaterQuality, WaterTank,
)


def _sync_thresholds_from_firebase():
    """Load the current Firebase threshold payload and mirror it into Django."""
    try:
        from iot.firebase_client import is_firebase_configured, read_path
    except Exception:
        return None

    if not is_firebase_configured():
        return None

    payload = read_path('config/thresholds') or {}
    if not isinstance(payload, dict):
        return None

    try:
        obj = MonitoringThreshold.objects.first()
        if obj is None:
            obj = MonitoringThreshold()

        ph = payload.get('ph') or {}
        tds = payload.get('tds') or {}
        turb = payload.get('turbidity') or {}
        battery = payload.get('battery') or {}

        obj.ph_normal_min = float(ph.get('min_normal', obj.ph_normal_min))
        obj.ph_normal_max = float(ph.get('max_normal', obj.ph_normal_max))
        obj.ph_danger_min = float(ph.get('min_warning', obj.ph_danger_min))
        obj.ph_danger_max = float(ph.get('max_warning', obj.ph_danger_max))
        obj.tds_normal_max = float(tds.get('max_normal', obj.tds_normal_max))
        obj.tds_danger_max = float(tds.get('max_warning', obj.tds_danger_max))
        obj.turbidity_normal_max = float(turb.get('max_normal', obj.turbidity_normal_max))
        obj.turbidity_danger_max = float(turb.get('max_warning', obj.turbidity_danger_max))
        obj.battery_warning_percent = float(battery.get('low_warning', obj.battery_warning_percent))
        obj.battery_critical_percent = float(battery.get('low_critical', obj.battery_critical_percent))
        obj.battery_empty_voltage = float(battery.get('empty_voltage', obj.battery_empty_voltage))
        obj.battery_full_voltage = float(battery.get('full_voltage', obj.battery_full_voltage))
        obj.device_offline_seconds = int(payload.get('device_offline_seconds', obj.device_offline_seconds))
        obj.save()
        return obj
    except Exception:
        return None


def _create_wq_alert(reading, user):
    if reading.warning_level == WarningLevel.NORMAL:
        return
    severity = {
        WarningLevel.FIRST: AlertSeverity.INFO,
        WarningLevel.MIDDLE: AlertSeverity.WARNING,
        WarningLevel.DANGER: AlertSeverity.CRITICAL,
    }[reading.warning_level]
    Notification.objects.create(
        title=f'Water Quality {reading.get_warning_level_display()}',
        message=(
            f'Abnormal water quality detected. pH={reading.ph}, TDS={reading.tds}, '
            f'Turbidity={reading.turbidity}, Temp={reading.temperature}°C. '
            f'Warning level: {reading.get_warning_level_display()}.'
        ),
        alert_type=AlertType.WATER_QUALITY,
        severity=severity,
    )


@login_required
@require_http_methods(['GET', 'POST'])
def threshold_settings(request):
    thresholds = MonitoringThreshold.objects.first()
    if thresholds is None:
        thresholds = MonitoringThreshold.objects.create()

    firebase_sync = _sync_thresholds_from_firebase()
    if firebase_sync is not None:
        thresholds = firebase_sync

    form = MonitoringThresholdForm(request.POST or None, instance=thresholds)
    if request.method == 'POST' and form.is_valid():
        thresholds = form.save()
        try:
            from iot.firebase_client import write_path
            write_path('config/thresholds', thresholds.as_dict())
            messages.success(request, 'Thresholds saved and synchronized to Firebase.')
        except Exception as exc:
            messages.warning(
                request,
                f'Thresholds saved locally, but Firebase sync failed: {exc}',
            )
        return redirect('monitoring:threshold_settings')
    return render(request, 'monitoring/threshold_settings.html', {
        'form': form,
        'thresholds': thresholds,
    })


# ---------- Water Quality ----------

@login_required
def water_quality_list(request):
    q = request.GET.get('q', '').strip()
    warning_level = request.GET.get('warning_level', '')
    qs = WaterQuality.objects.select_related('recorded_by').filter(
        recorded_at__lte=timezone.now(),
    )
    if warning_level:
        qs = qs.filter(warning_level=warning_level)
    if q:
        qs = qs.filter(notes__icontains=q)
    paginator = Paginator(qs, 15)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'monitoring/water_quality_list.html', {
        'page_obj': page,
        'q': q,
        'warning_level': warning_level,
        'warning_choices': WarningLevel,
    })


@login_required
def water_quality_detail(request, pk):
    obj = get_object_or_404(WaterQuality.objects.select_related('recorded_by'), pk=pk)
    display_notes = (
        '' if obj.notes.startswith('[SIMULATED DEMO') else obj.notes
    )
    return render(request, 'monitoring/water_quality_detail.html', {
        'object': obj,
        'display_notes': display_notes,
    })


@login_required
@require_http_methods(['GET', 'POST'])
def water_quality_create(request):
    form = WaterQualityForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        obj.recorded_by = request.user
        obj.save()
        _create_wq_alert(obj, request.user)
        messages.success(request, 'Water quality reading recorded.')
        return redirect('monitoring:water_quality_list')
    return render(request, 'monitoring/water_quality_form.html', {
        'form': form, 'title': 'Add Water Quality Reading',
    })


@login_required
@require_http_methods(['GET', 'POST'])
def water_quality_edit(request, pk):
    obj = get_object_or_404(WaterQuality, pk=pk)
    form = WaterQualityForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Water quality reading updated.')
        return redirect('monitoring:water_quality_list')
    return render(request, 'monitoring/water_quality_form.html', {
        'form': form, 'title': 'Edit Water Quality Reading', 'object': obj,
    })


@login_required
@require_http_methods(['POST'])
def water_quality_delete(request, pk):
    obj = get_object_or_404(WaterQuality, pk=pk)
    obj.delete()
    messages.success(request, 'Reading deleted.')
    return redirect('monitoring:water_quality_list')


# ---------- Water Tank ----------

@login_required
def tank_list(request):
    tanks = WaterTank.objects.all()
    return render(request, 'monitoring/tank_list.html', {'tanks': tanks})


@login_required
@require_http_methods(['GET', 'POST'])
def tank_create(request):
    form = WaterTankForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        tank = form.save()
        _check_tank_alerts(tank)
        messages.success(request, 'Tank added.')
        return redirect('monitoring:tank_list')
    return render(request, 'monitoring/tank_form.html', {
        'form': form, 'title': 'Add Water Tank',
    })


@login_required
@require_http_methods(['GET', 'POST'])
def tank_edit(request, pk):
    tank = get_object_or_404(WaterTank, pk=pk)
    form = WaterTankForm(request.POST or None, instance=tank)
    if request.method == 'POST' and form.is_valid():
        tank = form.save()
        _check_tank_alerts(tank)
        messages.success(request, 'Tank updated.')
        return redirect('monitoring:tank_list')
    return render(request, 'monitoring/tank_form.html', {
        'form': form, 'title': 'Edit Water Tank', 'object': tank,
    })


def _check_tank_alerts(tank):
    if tank.status == 'EMPTY':
        Notification.objects.create(
            title='Water Tank Empty',
            message=f'Tank "{tank.name}" is empty ({tank.current_level_percent}%).',
            alert_type=AlertType.TANK,
            severity=AlertSeverity.CRITICAL,
        )
    elif tank.status == 'LOW':
        Notification.objects.create(
            title='Water Tank Low',
            message=f'Tank "{tank.name}" is low ({tank.current_level_percent}%).',
            alert_type=AlertType.TANK,
            severity=AlertSeverity.WARNING,
        )
    elif tank.status == 'FULL':
        Notification.objects.create(
            title='Water Tank Full',
            message=f'Tank "{tank.name}" is full ({tank.current_level_percent}%).',
            alert_type=AlertType.TANK,
            severity=AlertSeverity.INFO,
        )


# ---------- Pump ----------

@login_required
def pump_list(request):
    pumps = Pump.objects.all()
    return render(request, 'monitoring/pump_list.html', {'pumps': pumps})


@login_required
@require_http_methods(['GET', 'POST'])
def pump_create(request):
    form = PumpForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        pump = form.save()
        _check_pump_alerts(pump)
        messages.success(request, 'Pump added.')
        return redirect('monitoring:pump_list')
    return render(request, 'monitoring/pump_form.html', {
        'form': form, 'title': 'Add Pump',
    })


@login_required
@require_http_methods(['GET', 'POST'])
def pump_edit(request, pk):
    pump = get_object_or_404(Pump, pk=pk)
    form = PumpForm(request.POST or None, instance=pump)
    if request.method == 'POST' and form.is_valid():
        pump = form.save()
        _check_pump_alerts(pump)
        messages.success(request, 'Pump updated.')
        return redirect('monitoring:pump_list')
    return render(request, 'monitoring/pump_form.html', {
        'form': form, 'title': 'Edit Pump', 'object': pump,
    })


def _check_pump_alerts(pump):
    if pump.pump_status == 'MALFUNCTION':
        Notification.objects.create(
            title='Pump Malfunction',
            message=f'Pump "{pump.name}" reported a malfunction.',
            alert_type=AlertType.PUMP,
            severity=AlertSeverity.CRITICAL,
        )


# ---------- Water Production ----------

@login_required
def production_list(request):
    qs = WaterProduction.objects.select_related('recorded_by').all()
    paginator = Paginator(qs, 15)
    page = paginator.get_page(request.GET.get('page'))

    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())
    stats = {
        'daily': WaterProduction.objects.filter(date=today).aggregate(
            t=Sum('daily_production_liters')
        )['t'] or 0,
        'weekly': WaterProduction.objects.filter(
            date__gte=week_start, date__lte=today
        ).aggregate(t=Sum('daily_production_liters'))['t'] or 0,
        'monthly': WaterProduction.objects.filter(
            date__year=today.year, date__month=today.month
        ).aggregate(t=Sum('daily_production_liters'))['t'] or 0,
        'total': WaterProduction.objects.aggregate(
            t=Sum('daily_production_liters')
        )['t'] or 0,
    }
    return render(request, 'monitoring/production_list.html', {
        'page_obj': page,
        'stats': stats,
    })


@login_required
@require_http_methods(['GET', 'POST'])
def production_create(request):
    form = WaterProductionForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        obj.recorded_by = request.user
        obj.save()
        messages.success(request, 'Production record saved.')
        return redirect('monitoring:production_list')
    return render(request, 'monitoring/production_form.html', {
        'form': form, 'title': 'Add Production Record',
    })


@login_required
@require_http_methods(['GET', 'POST'])
def production_edit(request, pk):
    obj = get_object_or_404(WaterProduction, pk=pk)
    form = WaterProductionForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Production record updated.')
        return redirect('monitoring:production_list')
    return render(request, 'monitoring/production_form.html', {
        'form': form, 'title': 'Edit Production Record', 'object': obj,
    })


@login_required
@require_http_methods(['POST'])
def production_delete(request, pk):
    obj = get_object_or_404(WaterProduction, pk=pk)
    obj.delete()
    messages.success(request, 'Production record deleted.')
    return redirect('monitoring:production_list')
