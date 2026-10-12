from django.contrib import admin
from .models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'report_type', 'report_format',
        'start_date', 'end_date', 'generated_by', 'created_at',
    )
    list_filter = ('report_type', 'report_format', 'created_at')
    search_fields = ('title', 'summary')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)
