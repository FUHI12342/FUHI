from django.urls import path
from . import views

app_name = 'attendance'

urlpatterns = [
    path('', views.MyAttendance.as_view(), name='my_attendance'),
    path('clock-in/<int:staff_pk>/', views.clock_in, name='clock_in'),
    path('clock-out/<int:staff_pk>/', views.clock_out, name='clock_out'),
    path('export/<int:store_pk>/<int:year>/<int:month>/', views.MonthlyCsvExport.as_view(), name='monthly_csv'),
]
