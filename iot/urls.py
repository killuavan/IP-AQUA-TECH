from django.urls import path
from . import views

app_name = 'iot'

urlpatterns = [
    path('', views.iot_dashboard, name='dashboard'),
    path('sync/', views.sync_now, name='sync_now'),
    path('demo-ingest/', views.demo_ingest, name='demo_ingest'),
    path('push-demo-firebase/', views.push_demo_firebase, name='push_demo_firebase'),
    path('devices/', views.device_list, name='device_list'),
    path('devices/add/', views.device_create, name='device_create'),
    path('devices/<int:pk>/edit/', views.device_edit, name='device_edit'),
    path('devices/<int:pk>/delete/', views.device_delete, name='device_delete'),
    path('sensors/', views.sensor_calibration_list, name='sensor_calibration_list'),
    path('sensors/add/', views.sensor_calibration_create, name='sensor_calibration_create'),
    path('sensors/<int:pk>/edit/', views.sensor_calibration_edit, name='sensor_calibration_edit'),
    path('sensors/<int:pk>/delete/', views.sensor_calibration_delete, name='sensor_calibration_delete'),
    path('sensors/seed/', views.sensor_calibration_seed, name='sensor_calibration_seed'),
    path('sync-logs/', views.sync_log_list, name='sync_log_list'),
    path('api/config/', views.firebase_config_js, name='firebase_config'),
    path('api/latest/', views.latest_live_api, name='latest_live'),
    path('api/ingest/', views.api_ingest, name='api_ingest'),
    path('api/heartbeat/', views.api_heartbeat, name='api_heartbeat'),
    path('api/calibrations/', views.api_calibrations, name='api_calibrations'),
]
