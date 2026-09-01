from django.contrib import admin
from .models import Seat, Schedule, Staff, Store, WalkIn


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ('name', 'business_type', 'opening_hour', 'closing_hour')


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ('name', 'store', 'kind', 'is_manager', 'sns_publishable', 'is_on_roster')
    list_filter = ('store', 'kind', 'is_manager', 'sns_publishable', 'is_on_roster')


@admin.register(Seat)
class SeatAdmin(admin.ModelAdmin):
    list_display = ('name', 'store', 'seat_type', 'capacity', 'is_active')
    list_filter = ('store', 'seat_type')


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ('name', 'staff', 'start', 'end', 'seat', 'party_size')
    list_filter = ('staff__store',)


@admin.register(WalkIn)
class WalkInAdmin(admin.ModelAdmin):
    list_display = ('seat', 'party_size', 'seated_at', 'left_at')
    list_filter = ('seat__store',)
