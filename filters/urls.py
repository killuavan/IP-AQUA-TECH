from django.urls import path
from . import views

app_name = 'filters'

urlpatterns = [
    path('', views.filter_list, name='filter_list'),
    path('add/', views.filter_create, name='filter_create'),
    path('<int:pk>/', views.filter_detail, name='filter_detail'),
    path('<int:pk>/edit/', views.filter_edit, name='filter_edit'),
    path('<int:pk>/delete/', views.filter_delete, name='filter_delete'),
]
