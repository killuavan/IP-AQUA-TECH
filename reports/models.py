"""
Report generation tracking models.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone


class ReportType(models.TextChoices):
    DAILY = 'DAILY', 'Daily Report'
    WEEKLY = 'WEEKLY', 'Weekly Report'
    MONTHLY = 'MONTHLY', 'Monthly Report'
    ANNUAL = 'ANNUAL', 'Annual Report'
    CUSTOM = 'CUSTOM', 'Custom Report'


class ReportFormat(models.TextChoices):
    PDF = 'PDF', 'PDF'
    EXCEL = 'EXCEL', 'Excel'
    BOTH = 'BOTH', 'PDF & Excel'


class Report(models.Model):
    """Generated report metadata."""

    title = models.CharField(max_length=200)
    report_type = models.CharField(
        max_length=20,
        choices=ReportType.choices,
        default=ReportType.DAILY,
    )
    report_format = models.CharField(
        max_length=10,
        choices=ReportFormat.choices,
        default=ReportFormat.PDF,
    )
    start_date = models.DateField()
    end_date = models.DateField()
    file_path = models.CharField(max_length=500, blank=True)
    file_pdf = models.FileField(upload_to='reports/pdf/', blank=True, null=True)
    file_excel = models.FileField(upload_to='reports/excel/', blank=True, null=True)
    summary = models.TextField(blank=True)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_reports',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Report'
        verbose_name_plural = 'Reports'

    def __str__(self):
        return f'{self.title} ({self.start_date} – {self.end_date})'
