"""IoT / Firebase views and API endpoints."""
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import models
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_GET, require_POST

from accounts.decorators import admin_required
from .firebase_client import get_web_config, is_firebase_configured, load_service_account_preview
from .models import IoTDevice, FirebaseSyncLog, SensorCalibration, SensorReadingCache
from .services import (
    create_demo_local_ingest,
    ingest_payload,
    mark_stale_devices_offline,
    pull_latest_from_firebase,
    push_demo_to_firebase,
    sync_from_firebase,
)
from .firebase_client import FirebaseNotConfigured


@login_required
def iot_dashboard(request):
    mark_stale_devices_offline()
    devices = IoTDevice.objects.all()
    recent_logs = FirebaseSyncLog.objects.all()[:10]
    recent_cache = SensorReadingCache.objects.select_related('device')[:15]
    online = devices.filter(status=IoTDevice.DeviceStatus.ONLINE).count()
    web_config = get_web_config()
    sa = load_service_account_preview()

    return render(request, 'iot/dashboard.html', {
        'devices': devices,
        'online_count': online,
        'recent_logs': recent_logs,
        'recent_cache': recent_cache,
        'firebase_configured': is_firebase_configured(),
        'firebase_web_config': web_config,
        'firebase_web_config_json': json.dumps(web_config),
        'service_account': sa,
    })


@login_required
@require_POST
def sync_now(request):
    log = sync_from_firebase(user=request.user)
    if log.status == FirebaseSyncLog.SyncStatus.SUCCESS:
        messages.success(request, log.message)
    elif log.status == FirebaseSyncLog.SyncStatus.SKIPPED:
        messages.warning(request, log.message)
    elif log.status == FirebaseSyncLog.SyncStatus.PARTIAL:
        messages.info(request, log.message)
    else:
        messages.error(request, f'Sync failed: {log.message}')
    return redirect('iot:dashboard')


@login_required
@require_POST
def demo_ingest(request):
    results = create_demo_local_ingest()
    messages.success(
        request,
        f'Demo IoT data ingested: {", ".join(k for k, v in results.items() if v) or "none"}',
    )
    return redirect('iot:dashboard')


@admin_required
@require_POST
def push_demo_firebase(request):
    try:
        result = push_demo_to_firebase()
        messages.success(request, f'Pushed demo data to Firebase: {len(result["written"])} paths.')
    except FirebaseNotConfigured as exc:
        messages.warning(request, str(exc))
    except Exception as exc:
        messages.error(request, f'Firebase push failed: {exc}')
    return redirect('iot:dashboard')


@login_required
def device_list(request):
    mark_stale_devices_offline()
    devices = IoTDevice.objects.all()
    online_count = devices.filter(status=IoTDevice.DeviceStatus.ONLINE).count()
    return render(request, 'iot/device_list.html', {
        'devices': devices,
        'online_count': online_count,
    })


@admin_required
@require_http_methods(['GET', 'POST'])
def device_create(request):
    from .forms import IoTDeviceForm
    form = IoTDeviceForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'IoT device registered.')
        return redirect('iot:device_list')
    return render(request, 'iot/device_form.html', {'form': form, 'title': 'Register IoT Device'})


@admin_required
@require_http_methods(['GET', 'POST'])
def device_edit(request, pk):
    from .forms import IoTDeviceForm
    device = get_object_or_404(IoTDevice, pk=pk)
    form = IoTDeviceForm(request.POST or None, instance=device)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Device updated.')
        return redirect('iot:device_list')
    return render(request, 'iot/device_form.html', {
        'form': form, 'title': 'Edit IoT Device', 'device': device,
    })


@admin_required
@require_POST
def device_delete(request, pk):
    device = get_object_or_404(IoTDevice, pk=pk)
    device.delete()
    messages.success(request, 'Device deleted.')
    return redirect('iot:device_list')


@login_required
def sync_log_list(request):
    qs = FirebaseSyncLog.objects.select_related('triggered_by').all()
    page = Paginator(qs, 20).get_page(request.GET.get('page'))
    return render(request, 'iot/sync_log_list.html', {'page_obj': page})


def _ensure_default_calibrations() -> int:
    """Create global defaults if missing. Returns how many were created."""
    defaults = [
        ('ph', 1.0, 0.0, 0.0, 14.0, 'pH probe'),
        ('tds', 1.0, 0.0, 0.0, 2000.0, 'TDS sensor'),
        ('turbidity', 1.0, 0.0, 0.0, 100.0, 'Turbidity sensor'),
        ('flow_rate', 1.0, 0.0, 0.0, None, 'Flow sensor'),
    ]
    created = 0
    for key, scale, offset, mn, mx, notes in defaults:
        defaults_dict = {
            'scale': scale,
            'offset': offset,
            'min_value': mn,
            'max_value': mx,
            'is_active': True,
            'notes': notes,
        }
        _, was_created = SensorCalibration.objects.get_or_create(
            device=None,
            sensor_key=key,
            defaults=defaults_dict,
        )
        if was_created:
            created += 1
    return created


@login_required
def sensor_calibration_list(request):
    """List + quick-edit sensor adjustments (scale / offset)."""
    # Auto-create main sensors so the page is ready to use
    seeded = _ensure_default_calibrations()
    if seeded:
        messages.info(request, f'Loaded {seeded} default sensor rows. Adjust scale/offset as needed.')

    calibrations = SensorCalibration.objects.select_related('device').exclude(
        sensor_key__in=('temperature', 'water_level'),
    )
    active_count = calibrations.filter(is_active=True).count()
    preview_raw = float(request.GET.get('raw') or 10)

    # Quick save from list page (inline adjust)
    if request.method == 'POST' and request.POST.get('action') == 'quick_save':
        try:
            pk = int(request.POST.get('pk'))
            cal = SensorCalibration.objects.get(pk=pk)
            cal.scale = float(request.POST.get('scale') or cal.scale)
            cal.offset = float(request.POST.get('offset') or cal.offset)
            cal.is_active = request.POST.get('is_active') == 'on'
            # optional min/max
            mn = request.POST.get('min_value', '').strip()
            mx = request.POST.get('max_value', '').strip()
            cal.min_value = float(mn) if mn != '' else None
            cal.max_value = float(mx) if mx != '' else None
            cal.save()
            messages.success(
                request,
                f'{cal.get_sensor_key_display()} updated: '
                f'scale={cal.scale}, offset={cal.offset}.',
            )
        except Exception as exc:
            messages.error(request, f'Could not save: {exc}')
        return redirect('iot:sensor_calibration_list')

    rows = []
    for c in calibrations:
        try:
            adjusted = c.apply(preview_raw) if c.is_active else preview_raw
        except Exception:
            adjusted = preview_raw
        rows.append({
            'cal': c,
            'preview_raw': preview_raw,
            'preview_out': round(float(adjusted), 4),
        })
    return render(request, 'iot/sensor_calibration_list.html', {
        'rows': rows,
        'calibrations': calibrations,
        'active_count': active_count,
        'preview_raw': preview_raw,
    })


@login_required
@require_http_methods(['GET', 'POST'])
def sensor_calibration_create(request):
    from .forms import SensorCalibrationForm
    form = SensorCalibrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Sensor adjustment saved. New IoT readings will use it.')
        return redirect('iot:sensor_calibration_list')
    return render(request, 'iot/sensor_calibration_form.html', {
        'form': form,
        'title': 'Add Sensor Adjustment',
    })


@login_required
@require_http_methods(['GET', 'POST'])
def sensor_calibration_edit(request, pk):
    from .forms import SensorCalibrationForm
    cal = get_object_or_404(SensorCalibration, pk=pk)
    form = SensorCalibrationForm(request.POST or None, instance=cal)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Sensor adjustment updated.')
        return redirect('iot:sensor_calibration_list')
    return render(request, 'iot/sensor_calibration_form.html', {
        'form': form,
        'title': 'Edit Sensor Adjustment',
        'calibration': cal,
    })


@login_required
@require_POST
def sensor_calibration_delete(request, pk):
    cal = get_object_or_404(SensorCalibration, pk=pk)
    cal.delete()
    messages.success(request, 'Sensor adjustment deleted.')
    return redirect('iot:sensor_calibration_list')


@login_required
@require_POST
def sensor_calibration_seed(request):
    """Create default global calibrations for main water sensors."""
    created = _ensure_default_calibrations()
    messages.success(
        request,
        f'Default calibrations ready ({created} new). Edit scale/offset as needed.',
    )
    return redirect('iot:sensor_calibration_list')


@login_required
@require_GET
def firebase_config_js(request):
    """Return public Firebase web config as JSON for dashboard live listeners."""
    return JsonResponse(get_web_config())


@login_required
@require_GET
def latest_live_api(request):
    """Pull Firebase latest nodes and return a web-friendly live snapshot."""
    mark_stale_devices_offline()
    types = ['water_quality', 'solar', 'battery', 'tank', 'pump']
    data = {}
    firebase_error = None

    if is_firebase_configured():
        try:
            result = pull_latest_from_firebase()
            for reading_type, payload in result['readings'].items():
                data[reading_type] = {
                    'payload': payload,
                    'source': 'firebase',
                    'live': True,
                    'received_at': payload.get('timestamp'),
                    'device': payload.get('device_id'),
                }
        except Exception as exc:
            firebase_error = str(exc)

    # Use the local cache if Firebase is temporarily unavailable or a sensor
    # group has not been returned by the current snapshot.
    for t in types:
        if t in data:
            continue
        row = SensorReadingCache.objects.filter(reading_type=t).first()
        if row:
            data[t] = {
                'payload': row.payload,
                'source': row.source,
                'live': False,
                'received_at': row.received_at.isoformat(),
                'device': row.device.device_id if row.device else None,
            }
    devices = list(
        IoTDevice.objects.filter(is_active=True).values(
            'name', 'device_id', 'status', 'last_seen', 'device_type'
        )
    )
    for d in devices:
        if d['last_seen']:
            d['last_seen'] = d['last_seen'].isoformat()
    response = JsonResponse({
        'firebase_configured': is_firebase_configured(),
        'firebase_error': firebase_error,
        'firebase_live': any(reading.get('live') for reading in data.values()),
        'readings': data,
        'devices': devices,
    })
    response['Cache-Control'] = 'no-store'
    return response


# ---------------------------------------------------------------------------
# Device API (ESP32 → Django) — API key auth, CSRF exempt
# ---------------------------------------------------------------------------

def _authenticate_device(request) -> IoTDevice | None:
    api_key = request.headers.get('X-API-Key') or request.META.get('HTTP_X_API_KEY')
    if not api_key:
        # Also allow ?api_key= for simple tests
        api_key = request.GET.get('api_key') or request.POST.get('api_key')
    if not api_key:
        return None
    try:
        return IoTDevice.objects.get(api_key=api_key, is_active=True)
    except IoTDevice.DoesNotExist:
        return None


@csrf_exempt
@require_http_methods(['POST'])
def api_ingest(request):
    """
    POST /iot/api/ingest/
    Headers: X-API-Key: <device api key>
    Body: JSON sensor payload
    """
    device = _authenticate_device(request)
    if not device:
        return JsonResponse({'ok': False, 'error': 'Invalid or missing API key'}, status=401)

    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)

    payload.setdefault('device_id', device.device_id)
    results = ingest_payload(payload, source='api')
    device.mark_seen(IoTDevice.DeviceStatus.ONLINE)

    return JsonResponse({
        'ok': True,
        'device_id': device.device_id,
        'ingested': results,
    })


@csrf_exempt
@require_http_methods(['POST', 'GET'])
def api_heartbeat(request):
    device = _authenticate_device(request)
    if not device:
        return JsonResponse({'ok': False, 'error': 'Unauthorized'}, status=401)
    device.mark_seen(IoTDevice.DeviceStatus.ONLINE)
    if request.method == 'POST':
        try:
            body = json.loads(request.body.decode('utf-8') or '{}')
            if body.get('firmware'):
                device.firmware_version = str(body['firmware'])[:50]
                device.save(update_fields=['firmware_version', 'updated_at'])
        except json.JSONDecodeError:
            pass
    return JsonResponse({
        'ok': True,
        'device_id': device.device_id,
        'server_time': __import__('django.utils.timezone', fromlist=['timezone']).timezone.now().isoformat(),
    })


@csrf_exempt
@require_GET
def api_calibrations(request):
    """
    GET /iot/api/calibrations/
    Headers: X-API-Key: <device api key>

    Returns active calibrations for this device + global ones.
    ESP can use scale/offset locally if desired.
    Server still applies calibration on ingest.
    """
    device = _authenticate_device(request)
    if not device:
        return JsonResponse({'ok': False, 'error': 'Unauthorized'}, status=401)

    qs = SensorCalibration.objects.filter(is_active=True).filter(
        models.Q(device=device) | models.Q(device__isnull=True)
    )
    # Prefer device-specific: list both; client can pick device first
    items = []
    for c in qs.select_related('device'):
        items.append({
            'sensor_key': c.sensor_key,
            'scale': c.scale,
            'offset': c.offset,
            'min_value': c.min_value,
            'max_value': c.max_value,
            'scope': 'device' if c.device_id else 'global',
            'formula': f'(raw * {c.scale}) + {c.offset}',
        })
    return JsonResponse({
        'ok': True,
        'device_id': device.device_id,
        'calibrations': items,
    })
