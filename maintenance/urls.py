from django.urls import path
from . import views

app_name = 'maintenance'

urlpatterns = [
    path('', views.maintenance_list, name='maintenance_list'),
    path('add/', views.maintenance_create, name='maintenance_create'),
    path('<int:pk>/', views.maintenance_detail, name='maintenance_detail'),
    path('<int:pk>/edit/', views.maintenance_edit, name='maintenance_edit'),
    path('<int:pk>/complete/', views.maintenance_complete, name='maintenance_complete'),
    path('<int:pk>/delete/', views.maintenance_delete, name='maintenance_delete'),
]
