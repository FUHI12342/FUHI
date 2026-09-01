from django.urls import path
from . import views

app_name = 'operations'

urlpatterns = [
    path('store/<int:store_pk>/today/', views.TodayDashboard.as_view(), name='dashboard'),
    path('task/<int:task_pk>/toggle/', views.toggle_task, name='toggle_task'),
    path('store/<int:store_pk>/open/', views.open_store, name='open_store'),
    path('store/<int:store_pk>/close/', views.close_store, name='close_store'),
]
