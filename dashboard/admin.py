from django.contrib import admin
from .models import SystemConfig


@admin.register(SystemConfig)
class SystemConfigAdmin(admin.ModelAdmin):
    list_display = ('name', 'overall_status', 'location', 'is_active', 'last_health_check')
    list_filter = ('overall_status', 'is_active')
