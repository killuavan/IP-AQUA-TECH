"""
Sync Firebase sensor data into Django monitoring models.
Also handles API/demo ingestion with the same mapping logic.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from filters.models import Filter
from monitoring.models import (
    WaterQuality, WaterTank, Pump, WaterProduction, WarningLevel,
    get_monitoring_thresholds,
)
from notifications.models import Notification, AlertType, AlertSeverity
from solar.models import SolarSystem, Battery, ChargingStatus

from .firebase_client import (
    FirebaseNotConfigured,
    is_firebase_configured,
    mirror_to_firestore,
    read_path,
    write_path,
)
from .models import FirebaseSyncLog, IoTDevice, SensorCalibration, SensorReadingCache

logger = logging.getLogger(__name__)


def _dec(value, default=None) -> Optional[Decimal]:
    if value is None or value == '':
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default


def apply_sensor_calibration(
    sensor_key: str,
    raw_value,
    device: Optional[IoTDevice] = None,
) -> Any:
    """
    Apply active SensorCalibration to a raw reading.

    Prefers device-specific calibration, then global (device=None).
    Formula: (raw × scale) + offset, then optional min/max clamp.
    """
    if raw_value is None or raw_value == '':
        return raw_value

    cal = None
    if device is not None:
        cal = SensorCalibration.objects.filter(
            device=device, sensor_key=sensor_key, is_active=True,
        ).first()
    if cal is None:
        cal = SensorCalibration.objects.filter(
            device__isnull=True, sensor_key=sensor_key, is_active=True,
        ).first()
    if cal is None:
        return raw_value
    try:
        return cal.apply(raw_value)
    except Exception:
        logger.exception('Calibration apply failed for %s', sensor_key)
        return raw_value


def _cal_dec(sensor_key: str, raw_value, device=None, default=None) -> Optional[Decimal]:
    adjusted = apply_sensor_calibration(sensor_key, raw_value, device)
    return _dec(adjusted, default)


def _water_level_percent(data: dict) -> Decimal:
    """Normalize ESP32 level status/probes to the model's percentage field."""
    numeric = _dec(data.get('water_level'))
    if numeric is not None:
        return numeric
    if data.get('water_high'):
        return Decimal('100')
    if data.get('water_mid'):
        return Decimal('66.67')
    if data.get('water_low'):
        return Decimal('33.33')
    return Decimal('0')


def _parse_ts(value) -> datetime:
    if not value:
        return timezone.now()
    if isinstance(value, (int, float)):
        # epoch seconds or ms
        ts = float(value)
        if ts > 1e12:
            ts /= 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.get_current_timezone())
    if isinstance(value, str):
        dt = parse_datetime(value)
        if dt:
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt)
            return dt
    return timezone.now()


def _get_device(device_id: Optional[str]) -> Optional[IoTDevice]:
    if not device_id:
        return None
    try:
        device = IoTDevice.objects.get(device_id=device_id)
        if not device.is_active:
            return None
        device.mark_seen(IoTDevice.DeviceStatus.ONLINE)
        return device
    except IoTDevice.DoesNotExist:
        device = IoTDevice.objects.create(
            device_id=device_id,
            name=f'Auto-registered {device_id}',
            device_type=IoTDevice.DeviceType.MULTI,
            status=IoTDevice.DeviceStatus.ONLINE,
            last_seen=timezone.now(),
        )
        return device


def _cache(reading_type: str, payload: dict, device=None, source='firebase'):
    SensorReadingCache.objects.create(
        device=device,
        reading_type=reading_type,
        payload=payload or {},
        source=source,
    )


def mark_stale_devices_offline() -> int:
    """Automatically mark active devices offline after no recent heartbeat."""
    seconds = int(get_monitoring_thresholds().get('device_offline_seconds', 60))
    cutoff = timezone.now() - timedelta(seconds=max(seconds, 10))
    return IoTDevice.objects.filter(
        is_active=True,
        last_seen__isnull=False,
        last_seen__lt=cutoff,
    ).exclude(
        status__in=[IoTDevice.DeviceStatus.OFFLINE, IoTDevice.DeviceStatus.MAINTENANCE]
    ).update(status=IoTDevice.DeviceStatus.OFFLINE, updated_at=timezone.now())


def _mark_device_error(device: Optional[IoTDevice], payload: dict) -> None:
    if device and payload.get('level_sensor_fault'):
        device.status = IoTDevice.DeviceStatus.ERROR
        device.save(update_fields=['status', 'updated_at'])


def ingest_water_quality(data: dict, source='firebase') -> Optional[WaterQuality]:
    if not data:
        return None
    device = _get_device(data.get('device_id'))
    _cache('water_quality', data, device, source)

    # Apply sensor calibration (scale/offset) before save
    previous_level = (
        WaterQuality.objects.values_list('warning_level', flat=True).first()
        or WarningLevel.NORMAL
    )
    obj = WaterQuality(
        ph=_cal_dec('ph', data.get('ph'), device, Decimal('7.0')),
        tds=_cal_dec('tds', data.get('tds'), device, Decimal('0')),
        turbidity=_cal_dec('turbidity', data.get('turbidity'), device, Decimal('0')),
        temperature=_cal_dec('temperature', data.get('temperature'), device, Decimal('25')),
        flow_rate=_cal_dec('flow_rate', data.get('flow_rate'), device, Decimal('0')),
        water_pressure=_cal_dec('water_pressure', data.get('water_pressure'), device, Decimal('0')),
        water_level=_water_level_percent(data),
        notes=data.get('notes', f'IoT ingest ({source})'),
        recorded_at=_parse_ts(data.get('timestamp')),
    )
    obj.save()
    _mark_device_error(device, data)

    # Notify on a transition to a new warning stage, not on every sample.
    if obj.warning_level != WarningLevel.NORMAL and obj.warning_level != previous_level:
        severity = {
            WarningLevel.FIRST: AlertSeverity.INFO,
            WarningLevel.MIDDLE: AlertSeverity.WARNING,
            WarningLevel.DANGER: AlertSeverity.CRITICAL,
        }[obj.warning_level]
        Notification.objects.create(
            title=f'IoT Water Quality {obj.get_warning_level_display()}',
            message=(
                f'Firebase/IoT reading: pH={obj.ph}, TDS={obj.tds}, '
                f'Turbidity={obj.turbidity}, '
                f'Warning={obj.get_warning_level_display()}'
            ),
            alert_type=AlertType.WATER_QUALITY,
            severity=severity,
        )
    return obj


def _update_battery_from_solar_voltage(voltage: Optional[Decimal], source='firebase') -> None:
    if voltage is None:
        return

    thresholds = get_monitoring_thresholds().get('battery', {})
    empty_voltage = Decimal(str(thresholds.get('empty_voltage', 11.8)))
    full_voltage = Decimal(str(thresholds.get('full_voltage', 12.7)))
    if full_voltage <= empty_voltage:
        return

    percentage = ((voltage - empty_voltage) / (full_voltage - empty_voltage)) * Decimal('100')
    percentage = max(Decimal('0'), min(Decimal('100'), percentage))
    battery = Battery.objects.first()
    if battery is None:
        battery = Battery(name='Main Battery Bank')
    previous_status = battery.status if battery.pk else None
    battery.voltage = voltage
    battery.percentage = percentage
    battery.notes = f'Voltage-derived battery update ({source})'
    battery.save()

    if battery.status in ('WARNING', 'CRITICAL') and battery.status != previous_status:
        Notification.objects.create(
            title=f'Battery {battery.get_status_display()}',
            message=f'Battery at {battery.percentage:.2f}% ({battery.voltage}V).',
            alert_type=AlertType.BATTERY,
            severity=(
                AlertSeverity.CRITICAL if battery.status == 'CRITICAL'
                else AlertSeverity.WARNING
            ),
        )


def ingest_solar(data: dict, source='firebase') -> Optional[SolarSystem]:
    if not data:
        return None
    device = _get_device(data.get('device_id'))
    _cache('solar', data, device, source)

    voltage_value = data.get('dc_voltage', data.get('panel_voltage'))
    voltage = _cal_dec('voltage', voltage_value, device, Decimal('0'))
    current = _cal_dec('current', data.get('panel_current'), device, Decimal('0'))
    power = _cal_dec('power', data.get('power_output'), device)
    if power is None and voltage is not None and current is not None:
        power = voltage * current

    obj = SolarSystem(
        panel_voltage=voltage,
        panel_current=current,
        power_output=power,
        power_consumption=_dec(data.get('power_consumption'), Decimal('0')),
        irradiance=_dec(data.get('irradiance')),
        panel_temperature=_dec(data.get('panel_temperature')),
        notes=data.get('notes', f'IoT ingest ({source})'),
        recorded_at=_parse_ts(data.get('timestamp')),
    )
    obj.save()
    _update_battery_from_solar_voltage(voltage, source)
    return obj


def ingest_battery(data: dict, source='firebase') -> Optional[Battery]:
    if not data:
        return None
    device = _get_device(data.get('device_id'))
    _cache('battery', data, device, source)

    charging = (data.get('charging_status') or 'IDLE').upper()
    valid = {c.value for c in ChargingStatus}
    if charging not in valid:
        charging = ChargingStatus.IDLE

    battery = Battery.objects.first()
    if battery is None:
        battery = Battery(name=data.get('name', 'Main Battery Bank'))
    previous_status = battery.status if battery.pk else None

    battery.voltage = _dec(data.get('voltage'), battery.voltage if battery.pk else Decimal('24'))
    battery.percentage = _dec(data.get('percentage'), Decimal('0'))
    battery.charging_status = charging
    if data.get('temperature') is not None:
        battery.temperature = _dec(data.get('temperature'))
    if data.get('health_percent') is not None:
        battery.health_percent = _dec(data.get('health_percent'))
    if data.get('capacity_ah') is not None:
        battery.capacity_ah = _dec(data.get('capacity_ah'))
    battery.notes = data.get('notes', f'IoT update ({source})')
    battery.save()

    if battery.status in ('WARNING', 'CRITICAL') and battery.status != previous_status:
        Notification.objects.create(
            title=f'IoT Battery {battery.get_status_display()}',
            message=f'Battery at {battery.percentage}% ({battery.voltage}V).',
            alert_type=AlertType.BATTERY,
            severity=(
                AlertSeverity.CRITICAL if battery.status == 'CRITICAL'
                else AlertSeverity.WARNING
            ),
        )
    return battery


def ingest_tank(data: dict, source='firebase') -> Optional[WaterTank]:
    if not data:
        return None
    device = _get_device(data.get('device_id'))
    _cache('tank', data, device, source)

    tank = WaterTank.objects.first()
    if tank is None:
        tank = WaterTank(name=data.get('name', 'Main Storage Tank'))

    if data.get('capacity_liters') is not None:
        tank.capacity_liters = _dec(data.get('capacity_liters'), tank.capacity_liters)
    tank.current_level_percent = _dec(data.get('level_percent') or data.get('current_level_percent'), Decimal('0'))
    tank.save()

    if tank.status in ('EMPTY', 'LOW'):
        Notification.objects.create(
            title=f'IoT Tank {tank.get_status_display()}',
            message=f'Tank "{tank.name}" level: {tank.current_level_percent}%.',
            alert_type=AlertType.TANK,
            severity=AlertSeverity.CRITICAL if tank.status == 'EMPTY' else AlertSeverity.WARNING,
        )
    return tank


def ingest_pump(data: dict, source='firebase') -> Optional[Pump]:
    if not data:
        return None
    device = _get_device(data.get('device_id'))
    _cache('pump', data, device, source)

    pump = Pump.objects.first()
    if pump is None:
        pump = Pump(name=data.get('name', 'Main Pump'))

    status_map = {
        'on': 'ON', 'off': 'OFF', 'malfunction': 'MALFUNCTION',
        'maintenance': 'MAINTENANCE', '1': 'ON', '0': 'OFF',
        True: 'ON', False: 'OFF',
    }

    def norm(v, default='OFF'):
        if v is None:
            return default
        if isinstance(v, bool):
            return 'ON' if v else 'OFF'
        key = str(v).lower()
        return status_map.get(key, str(v).upper() if str(v).upper() in ('ON', 'OFF', 'MALFUNCTION', 'MAINTENANCE') else default)

    pump.pump_status = norm(data.get('pump_status'), pump.pump_status)
    pump.uv_sterilizer_status = norm(data.get('uv_status') or data.get('uv_sterilizer_status'), pump.uv_sterilizer_status)
    pump.flow_status = norm(data.get('flow_status'), pump.flow_status)
    if data.get('system_pressure') is not None:
        pump.system_pressure = _dec(data.get('system_pressure'))
    if data.get('power_consumption') is not None:
        pump.power_consumption = _dec(data.get('power_consumption'))
    pump.notes = data.get('notes', f'IoT update ({source})')
    pump.save()
    _mark_device_error(device, data)

    if pump.pump_status == 'MALFUNCTION':
        Notification.objects.create(
            title='IoT Pump Malfunction',
            message=f'Pump "{pump.name}" reported malfunction via IoT.',
            alert_type=AlertType.PUMP,
            severity=AlertSeverity.CRITICAL,
        )
    return pump


def ingest_payload(payload: dict, source='api') -> dict:
    """
    Ingest a combined multi-sensor payload.

    Example:
    {
      "device_id": "esp32-001",
      "water_quality": {...},
      "solar": {...},
      "battery": {...},
      "tank": {...},
      "pump": {...}
    }
    """
    results = {}
    device_id = payload.get('device_id')
    if device_id:
        _get_device(device_id)

    sections = {
        'water_quality': ingest_water_quality,
        'solar': ingest_solar,
        'battery': ingest_battery,
        'tank': ingest_tank,
        'pump': ingest_pump,
    }
    for key, fn in sections.items():
        if key in payload and payload[key]:
            data = dict(payload[key])
            if device_id and 'device_id' not in data:
                data['device_id'] = device_id
            obj = fn(data, source=source)
            results[key] = bool(obj)

    # Flat single-type payloads
    if payload.get('ph') is not None and 'water_quality' not in payload:
        results['water_quality'] = bool(ingest_water_quality(payload, source=source))
    if payload.get('panel_voltage') is not None and 'solar' not in payload:
        results['solar'] = bool(ingest_solar(payload, source=source))

    return results


FIREBASE_LATEST_MAPPING = (
    ('water_quality', ingest_water_quality),
    ('solar', ingest_solar),
    ('battery', ingest_battery),
    ('tank', ingest_tank),
    ('pump', ingest_pump),
)


def _payload_fingerprint(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(',', ':'), default=str)


def pull_latest_from_firebase() -> dict:
    """
    Read the Firebase ``sensors`` tree and persist only changed ``latest`` nodes.

    This is shared by manual sync and the web live endpoint. Comparing each
    payload with the newest Firebase cache row prevents duplicate monitoring
    records and notifications when the browser polls faster than the ESP32.
    """
    sensors = read_path('sensors') or {}
    if not isinstance(sensors, dict):
        sensors = {}

    mirror_to_firestore('sensors', sensors)

    readings = {}
    details = {}
    imported = 0

    for label, ingest in FIREBASE_LATEST_MAPPING:
        group = sensors.get(label) or {}
        data = group.get('latest') if isinstance(group, dict) else None
        if not isinstance(data, dict) or not data:
            details[label] = 'no_data'
            continue

        readings[label] = data
        latest = SensorReadingCache.objects.filter(
            reading_type=label,
            source='firebase',
        ).first()
        if (
            latest
            and isinstance(latest.payload, dict)
            and _payload_fingerprint(latest.payload) == _payload_fingerprint(data)
        ):
            details[label] = 'unchanged'
            continue

        obj = ingest(data, source='firebase')
        if obj is not None:
            imported += 1
            details[label] = 'imported'
        else:
            details[label] = 'empty'

    return {
        'readings': readings,
        'imported': imported,
        'details': details,
    }


def sync_from_firebase(user=None) -> FirebaseSyncLog:
    """Pull latest readings from Firebase RTDB into Django models."""
    log = FirebaseSyncLog(triggered_by=user)
    details = {}
    imported = 0

    if not is_firebase_configured():
        log.status = FirebaseSyncLog.SyncStatus.SKIPPED
        log.message = (
            'Firebase not configured. Add firebase-service-account.json and '
            'FIREBASE_DATABASE_URL to enable sync.'
        )
        log.finished_at = timezone.now()
        log.save()
        return log

    try:
        result = pull_latest_from_firebase()
        imported = result['imported']
        details.update(result['details'])

        # Device last_seen from devices node
        try:
            devices = read_path('devices') or {}
            if isinstance(devices, dict):
                for did, meta in devices.items():
                    try:
                        device = IoTDevice.objects.get(device_id=did)
                        reported = str(meta.get('status', '')).upper() if isinstance(meta, dict) else ''
                        status = (
                            IoTDevice.DeviceStatus.ERROR
                            if reported == 'ERROR'
                            else IoTDevice.DeviceStatus.ONLINE
                        )
                        device.mark_seen(status)
                        if isinstance(meta, dict) and meta.get('firmware'):
                            device.firmware_version = str(meta.get('firmware'))
                            device.save(update_fields=['firmware_version', 'updated_at'])
                    except IoTDevice.DoesNotExist:
                        pass
        except Exception as exc:
            details['devices'] = f'error: {exc}'

        log.records_imported = imported
        log.details = details
        has_readings = bool(result['readings'])
        log.status = (
            FirebaseSyncLog.SyncStatus.SUCCESS if has_readings
            else FirebaseSyncLog.SyncStatus.PARTIAL
        )
        log.message = (
            f'Imported {imported} changed sensor group(s) from Firebase.'
            if imported
            else 'Firebase is connected; latest sensor data is already up to date.'
            if has_readings
            else 'Firebase is connected but has no sensor data yet.'
        )
    except FirebaseNotConfigured as exc:
        log.status = FirebaseSyncLog.SyncStatus.SKIPPED
        log.message = str(exc)
    except Exception as exc:
        logger.exception('Firebase sync failed')
        log.status = FirebaseSyncLog.SyncStatus.FAILED
        log.message = str(exc)
        log.details = details

    log.finished_at = timezone.now()
    log.save()
    return log


def push_demo_to_firebase() -> dict:
    """
    Write sample sensor values to Firebase (for testing the path structure).
    Requires configured credentials.
    """
    if not is_firebase_configured():
        raise FirebaseNotConfigured('Firebase not configured')

    now = timezone.now().isoformat()
    demo = {
        'sensors/water_quality/latest': {
            'ph': 7.15,
            'tds': 145,
            'turbidity': 0.4,
            'flow_rate': 12.2,
            'water_level': 60,
            'water_level_status': 'MEDIUM',
            'water_dirty': False,
            'level_sensor_fault': False,
            'device_id': 'esp32-001',
            'timestamp': now,
        },
        'sensors/solar/latest': {
            'panel_voltage': 28.4,
            'panel_current': 8.5,
            'power_output': 241.4,
            'power_consumption': 160,
            'irradiance': 780,
            'device_id': 'esp32-001',
            'timestamp': now,
        },
        'sensors/battery/latest': {
            'voltage': 24.8,
            'percentage': 82,
            'charging_status': 'CHARGING',
            'temperature': 29.0,
            'device_id': 'esp32-001',
            'timestamp': now,
        },
        'sensors/tank/latest': {
            'level_percent': 74,
            'capacity_liters': 2000,
            'device_id': 'esp32-001',
            'timestamp': now,
        },
        'sensors/pump/latest': {
            'pump_status': 'ON',
            'flow_status': 'ON',
            'water_level': 60,
            'water_level_status': 'MEDIUM',
            'water_dirty': False,
            'level_sensor_fault': False,
            'device_id': 'esp32-001',
            'timestamp': now,
        },
        'devices/esp32-001': {
            'name': 'Main Multi-Sensor Node',
            'type': 'MULTI',
            'firmware': '1.0.0',
            'last_seen': now,
        },
    }
    for path, data in demo.items():
        write_path(path, data)
    return {'written': list(demo.keys())}


def create_demo_local_ingest() -> dict:
    """Simulate IoT data without Firebase (local demo mode)."""
    now = timezone.now().isoformat()
    payload = {
        'device_id': 'esp32-demo',
        'water_quality': {
            'ph': 7.05,
            'tds': 160,
            'turbidity': 0.55,
            'temperature': 28.0,
            'flow_rate': 11.5,
            'water_pressure': 2.7,
            'water_level': 68,
            'water_level_status': 'MEDIUM',
            'water_dirty': False,
            'level_sensor_fault': False,
            'timestamp': now,
        },
        'solar': {
            'panel_voltage': 26.0,
            'panel_current': 7.2,
            'power_consumption': 150,
            'timestamp': now,
        },
        'battery': {
            'voltage': 24.2,
            'percentage': 71,
            'charging_status': 'CHARGING',
            'timestamp': now,
        },
        'tank': {
            'level_percent': 68,
            'timestamp': now,
        },
        'pump': {
            'pump_status': 'ON',
            'uv_status': 'ON',
            'flow_status': 'ON',
            'system_pressure': 2.9,
            'timestamp': now,
        },
    }
    # Ensure demo device exists
    IoTDevice.objects.get_or_create(
        device_id='esp32-demo',
        defaults={
            'name': 'Demo ESP32 Node',
            'device_type': IoTDevice.DeviceType.MULTI,
            'location': 'Lab / Demo',
            'status': IoTDevice.DeviceStatus.ONLINE,
            'firmware_version': 'demo-1.0',
        },
    )
    return ingest_payload(payload, source='demo')
