from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.notification_list, name='notification_list'),
    path('add/', views.notification_create, name='notification_create'),
    path('<int:pk>/read/', views.notification_mark_read, name='notification_mark_read'),
    path('<int:pk>/resolve/', views.notification_resolve, name='notification_resolve'),
    path('mark-all-read/', views.notification_mark_all_read, name='notification_mark_all_read'),
]
