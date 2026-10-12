from django.contrib import admin
from .models import WaterQuality, WaterTank, Pump, WaterProduction


@admin.register(WaterQuality)
class WaterQualityAdmin(admin.ModelAdmin):
    list_display = (
        'recorded_at', 'ph', 'tds', 'turbidity', 'temperature',
        'flow_rate', 'water_pressure', 'water_level', 'status', 'recorded_by',
    )
    list_filter = ('status', 'recorded_at')
    search_fields = ('notes',)
    date_hierarchy = 'recorded_at'
    readonly_fields = ('status', 'created_at')


@admin.register(WaterTank)
class WaterTankAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'capacity_liters', 'current_level_percent',
        'current_volume_liters', 'status', 'last_updated',
    )
    list_filter = ('status',)
    search_fields = ('name', 'location')


@admin.register(Pump)
class PumpAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'pump_status', 'uv_sterilizer_status',
        'system_pressure', 'flow_status', 'power_consumption', 'last_updated',
    )
    list_filter = ('pump_status', 'uv_sterilizer_status', 'flow_status')
    search_fields = ('name',)


@admin.register(WaterProduction)
class WaterProductionAdmin(admin.ModelAdmin):
    list_display = (
        'date', 'daily_production_liters', 'target_liters',
        'recorded_by', 'updated_at',
    )
    list_filter = ('date',)
    date_hierarchy = 'date'
    search_fields = ('notes',)
