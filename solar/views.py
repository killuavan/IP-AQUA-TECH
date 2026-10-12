"""Solar power and battery monitoring views."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from notifications.models import Notification, AlertType, AlertSeverity
from monitoring.models import get_monitoring_thresholds
from iot.models import SensorReadingCache
from .forms import SolarSystemForm, BatteryForm, SolarEnergyLogForm
from .models import SolarSystem, Battery, SolarEnergyLog, PowerStatus


def _solar_alerts(reading):
    if reading.status == PowerStatus.CRITICAL:
        Notification.objects.create(
            title='Solar Power Insufficient',
            message=(
                f'Solar power output is critically low: {reading.power_output}W '
                f'(Voltage: {reading.panel_voltage}V, Current: {reading.panel_current}A).'
            ),
            alert_type=AlertType.SOLAR,
            severity=AlertSeverity.CRITICAL,
        )
    elif reading.status == PowerStatus.WARNING:
        Notification.objects.create(
            title='Solar Power Warning',
            message=f'Solar power output is low: {reading.power_output}W.',
            alert_type=AlertType.SOLAR,
            severity=AlertSeverity.WARNING,
        )
    elif reading.status == PowerStatus.OFFLINE:
        Notification.objects.create(
            title='Solar System Offline',
            message='Solar panel system appears offline (zero power output).',
            alert_type=AlertType.SOLAR,
            severity=AlertSeverity.CRITICAL,
        )


def _battery_alerts(battery):
    if battery.status == PowerStatus.CRITICAL:
        Notification.objects.create(
            title='Battery Critically Low',
            message=f'Battery "{battery.name}" is at {battery.percentage}%.',
            alert_type=AlertType.BATTERY,
            severity=AlertSeverity.CRITICAL,
        )
    elif battery.status == PowerStatus.WARNING:
        Notification.objects.create(
            title='Battery Low',
            message=f'Battery "{battery.name}" is at {battery.percentage}%.',
            alert_type=AlertType.BATTERY,
            severity=AlertSeverity.WARNING,
        )


@login_required
def solar_list(request):
    qs = SolarSystem.objects.select_related('recorded_by').all()
    paginator = Paginator(qs, 15)
    page = paginator.get_page(request.GET.get('page'))
    latest = SolarSystem.objects.first()
    return render(request, 'solar/solar_list.html', {
        'page_obj': page,
        'latest': latest,
    })


@login_required
@require_http_methods(['GET', 'POST'])
def solar_create(request):
    form = SolarSystemForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        obj.recorded_by = request.user
        obj.save()
        _solar_alerts(obj)
        messages.success(request, 'Solar reading recorded.')
        return redirect('solar:solar_list')
    return render(request, 'solar/solar_form.html', {
        'form': form, 'title': 'Add Solar Reading',
    })


@login_required
@require_http_methods(['GET', 'POST'])
def solar_edit(request, pk):
    obj = get_object_or_404(SolarSystem, pk=pk)
    form = SolarSystemForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Solar reading updated.')
        return redirect('solar:solar_list')
    return render(request, 'solar/solar_form.html', {
        'form': form, 'title': 'Edit Solar Reading', 'object': obj,
    })


@login_required
@require_http_methods(['POST'])
def solar_delete(request, pk):
    obj = get_object_or_404(SolarSystem, pk=pk)
    obj.delete()
    messages.success(request, 'Solar reading deleted.')
    return redirect('solar:solar_list')


@login_required
def battery_list(request):
    batteries = Battery.objects.all()
    latest_solar = SolarSystem.objects.first()
    latest_solar_cache = SensorReadingCache.objects.filter(
        reading_type='solar', source='firebase',
    ).first()
    firebase_voltage = None
    if latest_solar_cache and isinstance(latest_solar_cache.payload, dict):
        firebase_voltage = latest_solar_cache.payload.get(
            'dc_voltage', latest_solar_cache.payload.get('panel_voltage'),
        )
    return render(request, 'solar/battery_list.html', {
        'batteries': batteries,
        'latest_solar': latest_solar,
        'firebase_voltage': firebase_voltage,
        'battery_thresholds': get_monitoring_thresholds().get('battery', {}),
    })


@login_required
@require_http_methods(['GET', 'POST'])
def battery_create(request):
    form = BatteryForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        battery = form.save()
        _battery_alerts(battery)
        messages.success(request, 'Battery added.')
        return redirect('solar:battery_list')
    return render(request, 'solar/battery_form.html', {
        'form': form, 'title': 'Add Battery',
    })


@login_required
@require_http_methods(['GET', 'POST'])
def battery_edit(request, pk):
    battery = get_object_or_404(Battery, pk=pk)
    form = BatteryForm(request.POST or None, instance=battery)
    if request.method == 'POST' and form.is_valid():
        battery = form.save()
        _battery_alerts(battery)
        messages.success(request, 'Battery updated.')
        return redirect('solar:battery_list')
    return render(request, 'solar/battery_form.html', {
        'form': form, 'title': 'Edit Battery', 'object': battery,
    })


@login_required
def energy_log_list(request):
    qs = SolarEnergyLog.objects.all()
    paginator = Paginator(qs, 15)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'solar/energy_log_list.html', {'page_obj': page})


@login_required
@require_http_methods(['GET', 'POST'])
def energy_log_create(request):
    form = SolarEnergyLogForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Energy log saved.')
        return redirect('solar:energy_log_list')
    return render(request, 'solar/energy_log_form.html', {
        'form': form, 'title': 'Add Energy Log',
    })
