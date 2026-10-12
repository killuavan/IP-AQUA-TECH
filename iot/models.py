"""
IoT device registry and Firebase sync logs.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone
import secrets


class IoTDevice(models.Model):
    """Registered sensor node (ESP32, etc.)."""

    class DeviceType(models.TextChoices):
        WATER_QUALITY = 'WATER_QUALITY', 'Water Quality Sensor'
        SOLAR = 'SOLAR', 'Solar Monitor'
        BATTERY = 'BATTERY', 'Battery Monitor'
        TANK = 'TANK', 'Tank Level Sensor'
        PUMP = 'PUMP', 'Pump Controller'
        MULTI = 'MULTI', 'Multi-Sensor Node'
        OTHER = 'OTHER', 'Other'

    class DeviceStatus(models.TextChoices):
        ONLINE = 'ONLINE', 'Online'
        OFFLINE = 'OFFLINE', 'Offline'
        ERROR = 'ERROR', 'Error'
        MAINTENANCE = 'MAINTENANCE', 'Maintenance'

    name = models.CharField(max_length=100)
    device_id = models.CharField(
        max_length=64,
        unique=True,
        help_text='Unique hardware ID used in Firebase paths',
    )
    device_type = models.CharField(
        max_length=20,
        choices=DeviceType.choices,
        default=DeviceType.MULTI,
    )
    api_key = models.CharField(max_length=64, unique=True, editable=False)
    firebase_path = models.CharField(
        max_length=200,
        blank=True,
        help_text='Firebase RTDB path, e.g. sensors/node1',
    )
    location = models.CharField(max_length=200, blank=True)
    status = models.CharField(
        max_length=20,
        choices=DeviceStatus.choices,
        default=DeviceStatus.OFFLINE,
    )
    is_active = models.BooleanField(default=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    firmware_version = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'IoT Device'
        verbose_name_plural = 'IoT Devices'

    def __str__(self):
        return f'{self.name} ({self.device_id})'

    def save(self, *args, **kwargs):
        if not self.api_key:
            self.api_key = secrets.token_hex(24)
        if not self.firebase_path:
            self.firebase_path = f'sensors/{self.device_id}'
        super().save(*args, **kwargs)

    def mark_seen(self, status=None):
        self.last_seen = timezone.now()
        if status:
            self.status = status
        elif self.status == self.DeviceStatus.OFFLINE:
            self.status = self.DeviceStatus.ONLINE
        self.save(update_fields=['last_seen', 'status', 'updated_at'])


class FirebaseSyncLog(models.Model):
    """Log of sync operations from Firebase → Django."""

    class SyncStatus(models.TextChoices):
        SUCCESS = 'SUCCESS', 'Success'
        PARTIAL = 'PARTIAL', 'Partial'
        FAILED = 'FAILED', 'Failed'
        SKIPPED = 'SKIPPED', 'Skipped (not configured)'

    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=SyncStatus.choices,
        default=SyncStatus.SUCCESS,
    )
    records_imported = models.PositiveIntegerField(default=0)
    message = models.TextField(blank=True)
    details = models.JSONField(default=dict, blank=True)
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='firebase_syncs',
    )

    class Meta:
        ordering = ['-started_at']
        verbose_name = 'Firebase Sync Log'
        verbose_name_plural = 'Firebase Sync Logs'

    def __str__(self):
        return f'Sync {self.started_at:%Y-%m-%d %H:%M} – {self.status}'


class SensorReadingCache(models.Model):
    """
    Latest raw payload received from Firebase / IoT devices.
    Useful for debugging and live status without re-querying Firebase.
    """

    device = models.ForeignKey(
        IoTDevice,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='readings',
    )
    reading_type = models.CharField(max_length=50)  # water_quality, solar, battery, tank, pump
    payload = models.JSONField(default=dict)
    source = models.CharField(
        max_length=20,
        default='firebase',
        help_text='firebase | api | demo',
    )
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-received_at']
        verbose_name = 'Sensor Reading Cache'
        verbose_name_plural = 'Sensor Reading Caches'

    def __str__(self):
        return f'{self.reading_type} @ {self.received_at:%Y-%m-%d %H:%M:%S}'


class SensorCalibration(models.Model):
    """
    Sensor adjustment applied to IoT readings before saving to monitoring.

    Formula: adjusted = (raw * scale) + offset
    Then optionally clamped to [min_value, max_value].
    """

    class SensorKey(models.TextChoices):
        PH = 'ph', 'pH'
        TDS = 'tds', 'TDS (ppm)'
        TURBIDITY = 'turbidity', 'Turbidity (NTU)'
        TEMPERATURE = 'temperature', 'Temperature (°C)'
        FLOW_RATE = 'flow_rate', 'Flow Rate'
        WATER_PRESSURE = 'water_pressure', 'Water Pressure'
        WATER_LEVEL = 'water_level', 'Water Level %'
        VOLTAGE = 'voltage', 'Solar Voltage'
        CURRENT = 'current', 'Solar Current'
        POWER = 'power', 'Solar Power'
        BATTERY_PERCENT = 'battery_percent', 'Battery %'
        TANK_LEVEL = 'tank_level', 'Tank Level %'

    device = models.ForeignKey(
        IoTDevice,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='calibrations',
        help_text='Leave empty to apply to all devices',
    )
    sensor_key = models.CharField(max_length=40, choices=SensorKey.choices)
    scale = models.FloatField(
        default=1.0,
        help_text='Multiplier (adjusted = raw × scale + offset)',
    )
    offset = models.FloatField(
        default=0.0,
        help_text='Additive offset after scale',
    )
    min_value = models.FloatField(
        null=True,
        blank=True,
        help_text='Optional minimum clamp',
    )
    max_value = models.FloatField(
        null=True,
        blank=True,
        help_text='Optional maximum clamp',
    )
    is_active = models.BooleanField(default=True)
    notes = models.CharField(max_length=200, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sensor_key', 'device_id']
        verbose_name = 'Sensor Calibration'
        verbose_name_plural = 'Sensor Calibrations'
        unique_together = [('device', 'sensor_key')]

    def __str__(self):
        scope = self.device.device_id if self.device_id else 'ALL'
        return f'{self.sensor_key} @ {scope} (×{self.scale} + {self.offset})'

    def apply(self, raw_value) -> float:
        """Apply scale/offset/clamp to a numeric reading."""
        try:
            val = float(raw_value) * float(self.scale) + float(self.offset)
        except (TypeError, ValueError):
            return raw_value
        if self.min_value is not None:
            val = max(float(self.min_value), val)
        if self.max_value is not None:
            val = min(float(self.max_value), val)
        return val
