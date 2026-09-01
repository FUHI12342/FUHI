import datetime

from django.shortcuts import get_object_or_404
from django.shortcuts import resolve_url
from django.test import TestCase
from django.utils import timezone

from booking.models import Schedule, Seat, Staff, Store
from booking.tests import batu, line, maru
from booking.timeslots import make_aware_datetime


class LateNightBusinessTests(TestCase):
    """深夜営業(閉店が翌日にまたがる店)のカレンダー・予約・座席ボード。"""
    fixtures = ['initial']

    def setUp(self):
        # 店舗Aを 18時-翌2時 営業に変更
        self.store = Store.objects.get(pk=1)
        self.store.opening_hour = 18
        self.store.closing_hour = 26
        self.store.save()

    def test_make_aware_datetime_rolls_over_midnight(self):
        dt = make_aware_datetime(2026, 9, 1, 25)
        local = timezone.localtime(dt)
        self.assertEqual((local.month, local.day, local.hour), (9, 2, 1))

    def test_business_slot_maps_early_morning_to_previous_day(self):
        local = timezone.localtime(make_aware_datetime(2026, 9, 1, 25))
        slot_date, slot_hour = self.store.business_slot(local)
        self.assertEqual((slot_date, slot_hour), (datetime.date(2026, 9, 1), 25))
        # 営業日当日の通常時刻はそのまま
        local = timezone.localtime(make_aware_datetime(2026, 9, 1, 19))
        self.assertEqual(self.store.business_slot(local), (datetime.date(2026, 9, 1), 19))

    def test_calendar_shows_late_night_rows_and_bookings(self):
        staff = get_object_or_404(Staff, pk=1)
        base = timezone.localdate() + datetime.timedelta(days=1)
        # 翌1時(=25時枠)の予約を入れる
        start = make_aware_datetime(base.year, base.month, base.day, 25)
        Schedule.objects.create(staff=staff, start=start, end=start + datetime.timedelta(hours=1), name='深夜客')
        response = self.client.get(
            resolve_url('booking:calendar', pk=1, year=base.year, month=base.month, day=base.day)
        )
        self.assertContains(response, '25:00')  # 深夜枠の行が表示される
        self.assertContains(response, batu)     # 25時枠が×になっている

    def test_booking_at_hour_25_creates_next_day_schedule(self):
        base = timezone.localdate() + datetime.timedelta(days=1)
        response = self.client.post(
            resolve_url('booking:booking', pk=1, year=base.year, month=base.month, day=base.day, hour=25),
            {'name': '深夜予約'}, follow=True,
        )
        self.assertEqual(response.status_code, 200)
        schedule = Schedule.objects.get(name='深夜予約')
        local = timezone.localtime(schedule.start)
        self.assertEqual(local.date(), base + datetime.timedelta(days=1))
        self.assertEqual(local.hour, 1)

    def test_seat_board_shows_late_night_reservation(self):
        seat = Seat.objects.create(store=self.store, name='VIP1', capacity=4)
        staff = get_object_or_404(Staff, pk=1)
        today = timezone.localdate()
        start = make_aware_datetime(today.year, today.month, today.day, 25)
        Schedule.objects.create(
            staff=staff, start=start, end=start + datetime.timedelta(hours=1),
            name='深夜卓', seat=seat, party_size=2,
        )
        self.client.login(username='tanakataro', password='helloworld123')
        response = self.client.get(resolve_url('booking:seat_board', pk=1))
        self.assertContains(response, '25:00')
        self.assertContains(response, '深夜卓(2名)')
