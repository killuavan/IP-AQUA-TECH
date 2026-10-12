"""
Filtration system models – filter condition and life tracking.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone
from datetime import timedelta


class FilterCondition(models.TextChoices):
    EXCELLENT = 'EXCELLENT', 'Excellent'
    GOOD = 'GOOD', 'Good'
    FAIR = 'FAIR', 'Fair'
    POOR = 'POOR', 'Poor'
    REPLACE = 'REPLACE', 'Needs Replacement'


class MaintenanceStatus(models.TextChoices):
    UP_TO_DATE = 'UP_TO_DATE', 'Up to Date'
    DUE_SOON = 'DUE_SOON', 'Due Soon'
    OVERDUE = 'OVERDUE', 'Overdue'


class Filter(models.Model):
    """Water filtration unit / cartridge tracking."""

    class FilterType(models.TextChoices):
        SEDIMENT = 'SEDIMENT', 'Sediment Filter'
        CARBON = 'CARBON', 'Carbon Filter'
        RO = 'RO', 'Reverse Osmosis Membrane'
        UV = 'UV', 'UV Lamp'
        CERAMIC = 'CERAMIC', 'Ceramic Filter'
        OTHER = 'OTHER', 'Other'

    name = models.CharField(max_length=100)
    filter_type = models.CharField(
        max_length=20,
        choices=FilterType.choices,
        default=FilterType.SEDIMENT,
    )
    condition = models.CharField(
        max_length=20,
        choices=FilterCondition.choices,
        default=FilterCondition.EXCELLENT,
    )
    life_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=100, help_text='Remaining life (%)'
    )
    install_date = models.DateField(default=timezone.localdate)
    expected_lifespan_days = models.PositiveIntegerField(default=180)
    next_replacement_date = models.DateField(null=True, blank=True)
    last_cleaned = models.DateField(null=True, blank=True)
    maintenance_status = models.CharField(
        max_length=20,
        choices=MaintenanceStatus.choices,
        default=MaintenanceStatus.UP_TO_DATE,
    )
    system_pressure = models.DecimalField(
        max_digits=6, decimal_places=2, default=0, help_text='Differential pressure (bar)'
    )
    flow_status = models.CharField(max_length=50, default='Normal')
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Filter'
        verbose_name_plural = 'Filters'

    def __str__(self):
        return f'{self.name} ({self.get_filter_type_display()}) – {self.life_percentage}%'

    def update_condition(self):
        life = float(self.life_percentage)
        if life <= 10:
            self.condition = FilterCondition.REPLACE
        elif life <= 25:
            self.condition = FilterCondition.POOR
        elif life <= 50:
            self.condition = FilterCondition.FAIR
        elif life <= 75:
            self.condition = FilterCondition.GOOD
        else:
            self.condition = FilterCondition.EXCELLENT

    def update_maintenance_status(self):
        if self.next_replacement_date:
            today = timezone.localdate()
            replacement = self.next_replacement_date
            if hasattr(replacement, 'date'):
                replacement = replacement.date()
            days_left = (replacement - today).days
            if days_left < 0:
                self.maintenance_status = MaintenanceStatus.OVERDUE
            elif days_left <= 14:
                self.maintenance_status = MaintenanceStatus.DUE_SOON
            else:
                self.maintenance_status = MaintenanceStatus.UP_TO_DATE
        life = float(self.life_percentage)
        thresholds = getattr(settings, 'FILTER_THRESHOLDS', {})
        if life <= thresholds.get('life_critical', 10):
            self.maintenance_status = MaintenanceStatus.OVERDUE
        elif life <= thresholds.get('life_warning', 25):
            if self.maintenance_status == MaintenanceStatus.UP_TO_DATE:
                self.maintenance_status = MaintenanceStatus.DUE_SOON

    def save(self, *args, **kwargs):
        if self.install_date and hasattr(self.install_date, 'date'):
            self.install_date = self.install_date.date()
        if not self.next_replacement_date and self.install_date:
            self.next_replacement_date = self.install_date + timedelta(
                days=self.expected_lifespan_days
            )
        elif self.next_replacement_date and hasattr(self.next_replacement_date, 'date'):
            self.next_replacement_date = self.next_replacement_date.date()
        self.update_condition()
        self.update_maintenance_status()
        super().save(*args, **kwargs)

    @property
    def needs_replacement(self):
        return (
            self.condition == FilterCondition.REPLACE
            or self.maintenance_status == MaintenanceStatus.OVERDUE
            or float(self.life_percentage) <= 10
        )
