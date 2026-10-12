from django.contrib import admin
from .models import SolarSystem, Battery, SolarEnergyLog


@admin.register(SolarSystem)
class SolarSystemAdmin(admin.ModelAdmin):
    list_display = (
        'recorded_at', 'panel_voltage', 'panel_current',
        'power_output', 'power_consumption', 'status', 'recorded_by',
    )
    list_filter = ('status', 'recorded_at')
    date_hierarchy = 'recorded_at'
    readonly_fields = ('status', 'created_at')


@admin.register(Battery)
class BatteryAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'voltage', 'percentage', 'charging_status',
        'health_percent', 'status', 'last_updated',
    )
    list_filter = ('charging_status', 'status')
    search_fields = ('name',)


@admin.register(SolarEnergyLog)
class SolarEnergyLogAdmin(admin.ModelAdmin):
    list_display = (
        'date', 'energy_generated_kwh', 'peak_power_w',
        'average_power_w', 'sunshine_hours',
    )
    date_hierarchy = 'date'
