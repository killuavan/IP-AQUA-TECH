from django.urls import path

from . import views

app_name = 'predictions'

urlpatterns = [
    path('', views.prediction_dashboard, name='dashboard'),
    path('run-monthly/', views.run_monthly, name='run_monthly'),
    path('train/', views.train_ml, name='train_ml'),
    path('history/monthly/', views.monthly_history, name='monthly_history'),
    path('weather/', views.weather_history, name='weather_history'),
]
