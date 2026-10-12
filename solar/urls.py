from django.urls import path
from . import views

app_name = 'solar'

urlpatterns = [
    path('', views.solar_list, name='solar_list'),
    path('add/', views.solar_create, name='solar_create'),
    path('<int:pk>/edit/', views.solar_edit, name='solar_edit'),
    path('<int:pk>/delete/', views.solar_delete, name='solar_delete'),
    path('batteries/', views.battery_list, name='battery_list'),
    path('batteries/add/', views.battery_create, name='battery_create'),
    path('batteries/<int:pk>/edit/', views.battery_edit, name='battery_edit'),
    path('energy-logs/', views.energy_log_list, name='energy_log_list'),
    path('energy-logs/add/', views.energy_log_create, name='energy_log_create'),
]
