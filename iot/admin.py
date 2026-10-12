from django.contrib import admin
from .models import IoTDevice, FirebaseSyncLog, SensorCalibration, SensorReadingCache


@admin.register(IoTDevice)
class IoTDeviceAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'device_id', 'device_type', 'status',
        'is_active', 'last_seen', 'firmware_version',
    )
    list_filter = ('device_type', 'status', 'is_active')
    search_fields = ('name', 'device_id', 'location', 'api_key')
    readonly_fields = ('api_key', 'created_at', 'updated_at', 'last_seen')


@admin.register(FirebaseSyncLog)
class FirebaseSyncLogAdmin(admin.ModelAdmin):
    list_display = ('started_at', 'status', 'records_imported', 'triggered_by', 'message')
    list_filter = ('status',)
    readonly_fields = ('started_at', 'finished_at', 'details')


@admin.register(SensorReadingCache)
class SensorReadingCacheAdmin(admin.ModelAdmin):
    list_display = ('reading_type', 'source', 'device', 'received_at')
    list_filter = ('reading_type', 'source')
    readonly_fields = ('payload', 'received_at')


@admin.register(SensorCalibration)
class SensorCalibrationAdmin(admin.ModelAdmin):
    list_display = (
        'sensor_key', 'device', 'scale', 'offset',
        'min_value', 'max_value', 'is_active', 'updated_at',
    )
    list_filter = ('sensor_key', 'is_active')
    search_fields = ('notes', 'device__name', 'device__device_id')
