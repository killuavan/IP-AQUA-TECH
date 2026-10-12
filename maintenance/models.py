"""
Maintenance management models.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone


class MaintenanceType(models.TextChoices):
    FILTER_REPLACEMENT = 'FILTER_REPLACEMENT', 'Filter Replacement'
    CLEANING = 'CLEANING', 'Cleaning'
    INSPECTION = 'INSPECTION', 'Inspection'
    REPAIR = 'REPAIR', 'Repair'
    CALIBRATION = 'CALIBRATION', 'Sensor Calibration'
    PUMP_SERVICE = 'PUMP_SERVICE', 'Pump Service'
    UV_SERVICE = 'UV_SERVICE', 'UV Sterilizer Service'
    BATTERY_SERVICE = 'BATTERY_SERVICE', 'Battery Service'
    OTHER = 'OTHER', 'Other'


class MaintenanceStatus(models.TextChoices):
    SCHEDULED = 'SCHEDULED', 'Scheduled'
    IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
    COMPLETED = 'COMPLETED', 'Completed'
    CANCELLED = 'CANCELLED', 'Cancelled'
    OVERDUE = 'OVERDUE', 'Overdue'


class MaintenancePriority(models.TextChoices):
    LOW = 'LOW', 'Low'
    MEDIUM = 'MEDIUM', 'Medium'
    HIGH = 'HIGH', 'High'
    URGENT = 'URGENT', 'Urgent'


class Maintenance(models.Model):
    """Maintenance task / work order."""

    title = models.CharField(max_length=200)
    maintenance_type = models.CharField(
        max_length=30,
        choices=MaintenanceType.choices,
        default=MaintenanceType.INSPECTION,
    )
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=MaintenanceStatus.choices,
        default=MaintenanceStatus.SCHEDULED,
    )
    priority = models.CharField(
        max_length=20,
        choices=MaintenancePriority.choices,
        default=MaintenancePriority.MEDIUM,
    )
    scheduled_date = models.DateField()
    completed_date = models.DateField(null=True, blank=True)
    assigned_technician = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_maintenance',
    )
    related_filter = models.ForeignKey(
        'filters.Filter',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='maintenance_tasks',
    )
    cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_maintenance',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-scheduled_date', '-priority']
        verbose_name = 'Maintenance Task'
        verbose_name_plural = 'Maintenance Tasks'

    def __str__(self):
        return f'{self.title} – {self.get_status_display()}'

    def check_overdue(self):
        if (
            self.status in (MaintenanceStatus.SCHEDULED, MaintenanceStatus.IN_PROGRESS)
            and self.scheduled_date < timezone.localdate()
        ):
            self.status = MaintenanceStatus.OVERDUE
            return True
        return False

    def mark_completed(self, user=None):
        self.status = MaintenanceStatus.COMPLETED
        self.completed_date = timezone.localdate()
        self.save()

    @property
    def is_overdue(self):
        return (
            self.status != MaintenanceStatus.COMPLETED
            and self.status != MaintenanceStatus.CANCELLED
            and self.scheduled_date < timezone.localdate()
        )
