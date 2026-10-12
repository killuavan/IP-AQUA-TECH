from django.contrib import admin
from .models import Filter


@admin.register(Filter)
class FilterAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'filter_type', 'condition', 'life_percentage',
        'maintenance_status', 'next_replacement_date', 'is_active',
    )
    list_filter = ('filter_type', 'condition', 'maintenance_status', 'is_active')
    search_fields = ('name', 'notes')
    readonly_fields = ('condition', 'maintenance_status', 'last_updated', 'created_at')
