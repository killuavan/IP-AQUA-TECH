"""
Dashboard app – no dedicated models; aggregates data from other apps.
SystemStatus can be used as a simple config/status singleton if needed.
"""
from django.db import models


class SystemConfig(models.Model):
    """Global system configuration / health snapshot."""

    class OverallStatus(models.TextChoices):
        OPERATIONAL = 'OPERATIONAL', 'Operational'
        DEGRADED = 'DEGRADED', 'Degraded'
        CRITICAL = 'CRITICAL', 'Critical'
        OFFLINE = 'OFFLINE', 'Offline'

    name = models.CharField(max_length=100, default='IP Aqua Tech System')
    overall_status = models.CharField(
        max_length=20,
        choices=OverallStatus.choices,
        default=OverallStatus.OPERATIONAL,
    )
    location = models.CharField(max_length=200, blank=True, default='Main Site')
    description = models.TextField(blank=True)
    last_health_check = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'System Configuration'
        verbose_name_plural = 'System Configurations'

    def __str__(self):
        return f'{self.name} – {self.get_overall_status_display()}'
