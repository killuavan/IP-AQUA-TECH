from django.contrib import admin
from .models import Maintenance


@admin.register(Maintenance)
class MaintenanceAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'maintenance_type', 'status', 'priority',
        'scheduled_date', 'assigned_technician', 'completed_date',
    )
    list_filter = ('status', 'priority', 'maintenance_type', 'scheduled_date')
    search_fields = ('title', 'description', 'notes')
    date_hierarchy = 'scheduled_date'
    raw_id_fields = ('assigned_technician', 'related_filter', 'created_by')
