from django.contrib import admin
from .models import Shift, TimeRecord


@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = ('date', 'staff', 'start_time', 'end_time', 'status')
    list_filter = ('status', 'staff__store', 'date')
    list_editable = ('status',)


@admin.register(TimeRecord)
class TimeRecordAdmin(admin.ModelAdmin):
    list_display = ('date', 'staff', 'clock_in', 'clock_out')
    list_filter = ('staff__store', 'date')
