from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.report_list, name='report_list'),
    path('generate/', views.report_generate, name='report_generate'),
    path('<int:pk>/', views.report_detail, name='report_detail'),
    path('<int:pk>/pdf/', views.report_download_pdf, name='report_download_pdf'),
    path('<int:pk>/excel/', views.report_download_excel, name='report_download_excel'),
    path('<int:pk>/delete/', views.report_delete, name='report_delete'),
]
