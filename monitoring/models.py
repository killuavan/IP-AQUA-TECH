"""
Water quality, tank, pump, and production monitoring models.
"""
from django.conf import settings
from django.db import models
from django.db.utils import OperationalError, ProgrammingError
from django.utils import timezone


class StatusChoices(models.TextChoices):
    NORMAL = 'NORMAL', 'Normal'
    WARNING = 'WARNING', 'Warning'
    CRITICAL = 'CRITICAL', 'Critical'


class WarningLevel(models.TextChoices):
    NORMAL = 'NORMAL', 'Normal'
    FIRST = 'FIRST', 'First Level Warning'
    MIDDLE = 'MIDDLE', 'Middle Level Warning'
    DANGER = 'DANGER', 'Danger Level Warning'


class MonitoringThreshold(models.Model):
    """Operator-editable thresholds shared by web classification and IoT."""

    ph_normal_min = models.FloatField(default=6.5)
    ph_normal_max = models.FloatField(default=8.5)
    ph_danger_min = models.FloatField(default=6.0)
    ph_danger_max = models.FloatField(default=9.0)
    tds_normal_max = models.FloatField(default=300.0)
    tds_danger_max = models.FloatField(default=500.0)
    turbidity_normal_max = models.FloatField(default=1.0)
    turbidity_danger_max = models.FloatField(default=5.0)
    battery_warning_percent = models.FloatField(default=30.0)
    battery_critical_percent = models.FloatField(default=15.0)
    battery_empty_voltage = models.FloatField(default=11.8)
    battery_full_voltage = models.FloatField(default=12.7)
    device_offline_seconds = models.PositiveIntegerField(default=60)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Monitoring Threshold'
        verbose_name_plural = 'Monitoring Thresholds'

    def __str__(self):
        return 'System monitoring thresholds'

    def as_dict(self):
        return {
            'ph': {
                'min_normal': self.ph_normal_min,
                'max_normal': self.ph_normal_max,
                'min_warning': self.ph_danger_min,
                'max_warning': self.ph_danger_max,
            },
            'tds': {
                'max_normal': self.tds_normal_max,
                'max_warning': self.tds_danger_max,
            },
            'turbidity': {
                'max_normal': self.turbidity_normal_max,
                'max_warning': self.turbidity_danger_max,
            },
            'battery': {
                'low_warning': self.battery_warning_percent,
                'low_critical': self.battery_critical_percent,
                'empty_voltage': self.battery_empty_voltage,
                'full_voltage': self.battery_full_voltage,
            },
            'device_offline_seconds': self.device_offline_seconds,
        }


def get_monitoring_thresholds():
    defaults = getattr(settings, 'WATER_QUALITY_THRESHOLDS', {}).copy()
    defaults['battery'] = getattr(settings, 'BATTERY_THRESHOLDS', {}).copy()
    defaults['device_offline_seconds'] = 60
    try:
        configured = MonitoringThreshold.objects.first()
    except (OperationalError, ProgrammingError):
        configured = None
    return configured.as_dict() if configured else defaults


class WaterQuality(models.Model):
    """Record of water quality sensor readings."""

    ph = models.DecimalField(max_digits=4, decimal_places=2, help_text='pH level (0-14)')
    tds = models.DecimalField(max_digits=8, decimal_places=2, help_text='Total Dissolved Solids (ppm)')
    turbidity = models.DecimalField(max_digits=6, decimal_places=2, help_text='Turbidity (NTU)')
    temperature = models.DecimalField(max_digits=5, decimal_places=2, help_text='Temperature (°C)')
    flow_rate = models.DecimalField(max_digits=8, decimal_places=2, help_text='Flow rate (L/min)')
    water_pressure = models.DecimalField(max_digits=6, decimal_places=2, help_text='Water pressure (bar)')
    water_level = models.DecimalField(max_digits=5, decimal_places=2, help_text='Water level (%)')
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.NORMAL,
    )
    warning_level = models.CharField(
        max_length=20,
        choices=WarningLevel.choices,
        default=WarningLevel.NORMAL,
    )
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='water_quality_records',
    )
    recorded_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_at']
        verbose_name = 'Water Quality Reading'
        verbose_name_plural = 'Water Quality Readings'

    def __str__(self):
        return f'WQ {self.recorded_at:%Y-%m-%d %H:%M} – {self.status}'

    def classify_status(self):
        """Classify overall status based on thresholds."""
        thresholds = get_monitoring_thresholds()
        statuses = []

        ph_t = thresholds.get('ph', {})
        ph = float(self.ph)
        if ph < ph_t.get('min_warning', 6.0) or ph > ph_t.get('max_warning', 9.0):
            statuses.append(StatusChoices.CRITICAL)
        elif ph < ph_t.get('min_normal', 6.5) or ph > ph_t.get('max_normal', 8.5):
            statuses.append(StatusChoices.WARNING)
        else:
            statuses.append(StatusChoices.NORMAL)

        tds_t = thresholds.get('tds', {})
        tds = float(self.tds)
        if tds > tds_t.get('max_warning', 500):
            statuses.append(StatusChoices.CRITICAL)
        elif tds > tds_t.get('max_normal', 300):
            statuses.append(StatusChoices.WARNING)
        else:
            statuses.append(StatusChoices.NORMAL)

        turb_t = thresholds.get('turbidity', {})
        turb = float(self.turbidity)
        if turb > turb_t.get('max_warning', 5.0):
            statuses.append(StatusChoices.CRITICAL)
        elif turb > turb_t.get('max_normal', 1.0):
            statuses.append(StatusChoices.WARNING)
        else:
            statuses.append(StatusChoices.NORMAL)

        temp_t = thresholds.get('temperature', {})
        temp = float(self.temperature)
        if temp < temp_t.get('min_warning', 5) or temp > temp_t.get('max_warning', 40):
            statuses.append(StatusChoices.CRITICAL)
        elif temp < temp_t.get('min_normal', 10) or temp > temp_t.get('max_normal', 35):
            statuses.append(StatusChoices.WARNING)
        else:
            statuses.append(StatusChoices.NORMAL)

        if StatusChoices.CRITICAL in statuses:
            return StatusChoices.CRITICAL
        if StatusChoices.WARNING in statuses:
            return StatusChoices.WARNING
        return StatusChoices.NORMAL

    def classify_warning_level(self):
        """Return First, Middle, or Danger based on distance from normal."""
        thresholds = get_monitoring_thresholds()

        def high_level(value, normal_max, danger_max):
            if value > danger_max:
                return 3
            if value > normal_max:
                midpoint = normal_max + ((danger_max - normal_max) / 2.0)
                return 2 if value > midpoint else 1
            return 0

        ph = float(self.ph)
        ph_t = thresholds.get('ph', {})
        ph_level = 0
        if ph < ph_t.get('min_warning', 6.0) or ph > ph_t.get('max_warning', 9.0):
            ph_level = 3
        elif ph < ph_t.get('min_normal', 6.5):
            midpoint = (ph_t.get('min_warning', 6.0) + ph_t.get('min_normal', 6.5)) / 2.0
            ph_level = 2 if ph < midpoint else 1
        elif ph > ph_t.get('max_normal', 8.5):
            midpoint = (ph_t.get('max_normal', 8.5) + ph_t.get('max_warning', 9.0)) / 2.0
            ph_level = 2 if ph > midpoint else 1

        tds_t = thresholds.get('tds', {})
        turb_t = thresholds.get('turbidity', {})
        level = max(
            ph_level,
            high_level(float(self.tds), tds_t.get('max_normal', 300), tds_t.get('max_warning', 500)),
            high_level(float(self.turbidity), turb_t.get('max_normal', 1), turb_t.get('max_warning', 5)),
        )
        return {
            0: WarningLevel.NORMAL,
            1: WarningLevel.FIRST,
            2: WarningLevel.MIDDLE,
            3: WarningLevel.DANGER,
        }[level]

    def save(self, *args, **kwargs):
        self.warning_level = self.classify_warning_level()
        self.status = (
            StatusChoices.CRITICAL
            if self.warning_level == WarningLevel.DANGER
            else StatusChoices.WARNING
            if self.warning_level in (WarningLevel.FIRST, WarningLevel.MIDDLE)
            else StatusChoices.NORMAL
        )
        super().save(*args, **kwargs)

    @property
    def is_abnormal(self):
        return self.status in (StatusChoices.WARNING, StatusChoices.CRITICAL)


class WaterTank(models.Model):
    """Water tank level and capacity tracking."""

    class TankStatus(models.TextChoices):
        EMPTY = 'EMPTY', 'Empty'
        LOW = 'LOW', 'Low'
        NORMAL = 'NORMAL', 'Normal'
        FULL = 'FULL', 'Full'

    name = models.CharField(max_length=100, default='Main Storage Tank')
    capacity_liters = models.DecimalField(max_digits=10, decimal_places=2, default=1000)
    current_level_percent = models.DecimalField(max_digits=5, decimal_places=2, default=50)
    current_volume_liters = models.DecimalField(max_digits=10, decimal_places=2, default=500)
    status = models.CharField(
        max_length=20,
        choices=TankStatus.choices,
        default=TankStatus.NORMAL,
    )
    location = models.CharField(max_length=200, blank=True)
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Water Tank'
        verbose_name_plural = 'Water Tanks'

    def __str__(self):
        return f'{self.name} ({self.current_level_percent}%)'

    def update_status(self):
        level = float(self.current_level_percent)
        if level <= 5:
            self.status = self.TankStatus.EMPTY
        elif level <= 20:
            self.status = self.TankStatus.LOW
        elif level >= 95:
            self.status = self.TankStatus.FULL
        else:
            self.status = self.TankStatus.NORMAL

    def save(self, *args, **kwargs):
        self.current_volume_liters = (
            float(self.capacity_liters) * float(self.current_level_percent) / 100
        )
        self.update_status()
        super().save(*args, **kwargs)


class Pump(models.Model):
    """Pump / UV sterilizer operational status."""

    class DeviceStatus(models.TextChoices):
        ON = 'ON', 'On'
        OFF = 'OFF', 'Off'
        MALFUNCTION = 'MALFUNCTION', 'Malfunction'
        MAINTENANCE = 'MAINTENANCE', 'Under Maintenance'

    name = models.CharField(max_length=100, default='Main Pump')
    pump_status = models.CharField(
        max_length=20,
        choices=DeviceStatus.choices,
        default=DeviceStatus.OFF,
    )
    uv_sterilizer_status = models.CharField(
        max_length=20,
        choices=DeviceStatus.choices,
        default=DeviceStatus.OFF,
    )
    system_pressure = models.DecimalField(
        max_digits=6, decimal_places=2, default=0, help_text='System pressure (bar)'
    )
    flow_status = models.CharField(
        max_length=20,
        choices=DeviceStatus.choices,
        default=DeviceStatus.OFF,
    )
    power_consumption = models.DecimalField(
        max_digits=8, decimal_places=2, default=0, help_text='Power consumption (W)'
    )
    runtime_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Pump'
        verbose_name_plural = 'Pumps'

    def __str__(self):
        return f'{self.name} – Pump: {self.pump_status}'

    @property
    def is_operational(self):
        return self.pump_status == self.DeviceStatus.ON


class WaterProduction(models.Model):
    """Daily water production records."""

    date = models.DateField(unique=True)
    daily_production_liters = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    target_liters = models.DecimalField(max_digits=10, decimal_places=2, default=500)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='production_records',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']
        verbose_name = 'Water Production'
        verbose_name_plural = 'Water Production Records'

    def __str__(self):
        return f'{self.date}: {self.daily_production_liters} L'

    @property
    def target_met(self):
        return float(self.daily_production_liters) >= float(self.target_liters)
