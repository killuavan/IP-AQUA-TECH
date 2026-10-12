from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'alert_type', 'severity', 'is_read',
        'is_resolved', 'recipient', 'created_at',
    )
    list_filter = ('alert_type', 'severity', 'is_read', 'is_resolved', 'created_at')
    search_fields = ('title', 'message')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)
