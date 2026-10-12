"""
Alerts and notifications models.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone


class AlertType(models.TextChoices):
    WATER_QUALITY = 'WATER_QUALITY', 'Water Quality'
    FILTER = 'FILTER', 'Filter'
    BATTERY = 'BATTERY', 'Battery'
    SOLAR = 'SOLAR', 'Solar Power'
    TANK = 'TANK', 'Water Tank'
    PUMP = 'PUMP', 'Pump'
    SENSOR = 'SENSOR', 'Sensor Failure'
    MAINTENANCE = 'MAINTENANCE', 'Maintenance'
    SYSTEM = 'SYSTEM', 'System'
    OTHER = 'OTHER', 'Other'


class AlertSeverity(models.TextChoices):
    INFO = 'INFO', 'Info'
    WARNING = 'WARNING', 'Warning'
    CRITICAL = 'CRITICAL', 'Critical'


class Notification(models.Model):
    """System alert / notification."""

    title = models.CharField(max_length=200)
    message = models.TextField()
    alert_type = models.CharField(
        max_length=20,
        choices=AlertType.choices,
        default=AlertType.SYSTEM,
    )
    severity = models.CharField(
        max_length=20,
        choices=AlertSeverity.choices,
        default=AlertSeverity.INFO,
    )
    is_read = models.BooleanField(default=False)
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_notifications',
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
        help_text='Leave blank for system-wide alerts',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'

    def __str__(self):
        return f'[{self.severity}] {self.title}'

    def mark_read(self):
        self.is_read = True
        self.save(update_fields=['is_read'])

    def resolve(self, user=None):
        self.is_resolved = True
        self.is_read = True
        self.resolved_at = timezone.now()
        self.resolved_by = user
        self.save()
