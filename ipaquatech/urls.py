"""
URL configuration for IP Aqua Tech project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('dashboard.urls')),
    path('accounts/', include('accounts.urls')),
    path('monitoring/', include('monitoring.urls')),
    path('solar/', include('solar.urls')),
    path('filters/', include('filters.urls')),
    path('maintenance/', include('maintenance.urls')),
    path('reports/', include('reports.urls')),
    path('notifications/', include('notifications.urls')),
    path('iot/', include('iot.urls')),
    path('predictions/', include('predictions.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])

# Admin branding
admin.site.site_header = 'IP Aqua Tech Administration'
admin.site.site_title = 'IP Aqua Tech Admin'
admin.site.index_title = 'System Administration'
