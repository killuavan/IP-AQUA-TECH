"""
Solar power and battery monitoring models.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone


class ChargingStatus(models.TextChoices):
    CHARGING = 'CHARGING', 'Charging'
    DISCHARGING = 'DISCHARGING', 'Discharging'
    FULL = 'FULL', 'Full'
    IDLE = 'IDLE', 'Idle'
    FAULT = 'FAULT', 'Fault'


class PowerStatus(models.TextChoices):
    NORMAL = 'NORMAL', 'Normal'
    WARNING = 'WARNING', 'Warning'
    CRITICAL = 'CRITICAL', 'Critical'
    OFFLINE = 'OFFLINE', 'Offline'


class SolarSystem(models.Model):
    """Solar panel system readings."""

    panel_voltage = models.DecimalField(max_digits=8, decimal_places=2, help_text='Panel voltage (V)')
    panel_current = models.DecimalField(max_digits=8, decimal_places=2, help_text='Panel current (A)')
    power_output = models.DecimalField(max_digits=10, decimal_places=2, help_text='Power output (W)')
    power_consumption = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, help_text='System power consumption (W)'
    )
    status = models.CharField(
        max_length=20,
        choices=PowerStatus.choices,
        default=PowerStatus.NORMAL,
    )
    irradiance = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True, help_text='Solar irradiance (W/m²)'
    )
    panel_temperature = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, help_text='Panel temperature (°C)'
    )
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='solar_records',
    )
    recorded_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_at']
        verbose_name = 'Solar System Reading'
        verbose_name_plural = 'Solar System Readings'

    def __str__(self):
        return f'Solar {self.recorded_at:%Y-%m-%d %H:%M} – {self.power_output}W'

    def calculate_power(self):
        return float(self.panel_voltage) * float(self.panel_current)

    def classify_status(self):
        power = float(self.power_output)
        if power <= 0:
            return PowerStatus.OFFLINE
        if power < 50:
            return PowerStatus.CRITICAL
        if power < 150:
            return PowerStatus.WARNING
        return PowerStatus.NORMAL

    def save(self, *args, **kwargs):
        if not self.power_output or float(self.power_output) == 0:
            self.power_output = self.calculate_power()
        self.status = self.classify_status()
        super().save(*args, **kwargs)


class Battery(models.Model):
    """Battery bank status and readings."""

    name = models.CharField(max_length=100, default='Main Battery Bank')
    voltage = models.DecimalField(max_digits=6, decimal_places=2, help_text='Battery voltage (V)')
    percentage = models.DecimalField(max_digits=5, decimal_places=2, help_text='Charge percentage (%)')
    charging_status = models.CharField(
        max_length=20,
        choices=ChargingStatus.choices,
        default=ChargingStatus.IDLE,
    )
    capacity_ah = models.DecimalField(
        max_digits=8, decimal_places=2, default=100, help_text='Capacity (Ah)'
    )
    temperature = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, help_text='Battery temp (°C)'
    )
    health_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=100, help_text='Battery health (%)'
    )
    cycle_count = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=PowerStatus.choices,
        default=PowerStatus.NORMAL,
    )
    notes = models.TextField(blank=True)
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Battery'
        verbose_name_plural = 'Batteries'

    def __str__(self):
        return f'{self.name} – {self.percentage}% ({self.charging_status})'

    def classify_status(self):
        # Import here to avoid a models import cycle.
        from monitoring.models import get_monitoring_thresholds
        thresholds = get_monitoring_thresholds().get('battery', {})
        pct = float(self.percentage)
        if pct <= thresholds.get('low_critical', 15):
            return PowerStatus.CRITICAL
        if pct <= thresholds.get('low_warning', 30):
            return PowerStatus.WARNING
        if self.charging_status == ChargingStatus.FAULT:
            return PowerStatus.CRITICAL
        return PowerStatus.NORMAL

    def save(self, *args, **kwargs):
        self.status = self.classify_status()
        super().save(*args, **kwargs)


class SolarEnergyLog(models.Model):
    """Daily solar energy generation log for charts/reports."""

    date = models.DateField(unique=True)
    energy_generated_kwh = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    peak_power_w = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    average_power_w = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    sunshine_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']
        verbose_name = 'Solar Energy Log'
        verbose_name_plural = 'Solar Energy Logs'

    def __str__(self):
        return f'{self.date}: {self.energy_generated_kwh} kWh'
