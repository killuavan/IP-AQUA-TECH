from django.urls import path
from . import views

app_name = 'monitoring'

urlpatterns = [
    path('thresholds/', views.threshold_settings, name='threshold_settings'),
    # Water quality
    path('water-quality/', views.water_quality_list, name='water_quality_list'),
    path('water-quality/add/', views.water_quality_create, name='water_quality_create'),
    path('water-quality/<int:pk>/', views.water_quality_detail, name='water_quality_detail'),
    path('water-quality/<int:pk>/edit/', views.water_quality_edit, name='water_quality_edit'),
    path('water-quality/<int:pk>/delete/', views.water_quality_delete, name='water_quality_delete'),
    # Tank
    path('tanks/', views.tank_list, name='tank_list'),
    path('tanks/add/', views.tank_create, name='tank_create'),
    path('tanks/<int:pk>/edit/', views.tank_edit, name='tank_edit'),
    # Pump
    path('pumps/', views.pump_list, name='pump_list'),
    path('pumps/add/', views.pump_create, name='pump_create'),
    path('pumps/<int:pk>/edit/', views.pump_edit, name='pump_edit'),
    # Production
    path('production/', views.production_list, name='production_list'),
    path('production/add/', views.production_create, name='production_create'),
    path('production/<int:pk>/edit/', views.production_edit, name='production_edit'),
    path('production/<int:pk>/delete/', views.production_delete, name='production_delete'),
]
