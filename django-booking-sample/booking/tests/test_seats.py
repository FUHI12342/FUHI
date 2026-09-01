import datetime

from django.db import IntegrityError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.shortcuts import resolve_url
from django.test import TestCase
from django.utils import timezone

from booking.models import Schedule, Seat, Staff, Store, WalkIn


class SeatBoardViewTests(TestCase):
    fixtures = ['initial']

    def setUp(self):
        self.store = Store.objects.get(pk=1)
        self.seat = Seat.objects.create(store=self.store, name='T1', capacity=4)

    def test_requires_store_membership(self):
        self.client.login(username='yosidaziro', password='helloworld123')
        response = self.client.get(resolve_url('booking:seat_board', pk=2))
        self.assertEqual(response.status_code, 403)

    def test_board_shows_seat_and_reservation(self):
        staff = get_object_or_404(Staff, pk=1)
        now = timezone.localtime().replace(hour=10, minute=0, second=0, microsecond=0)
        Schedule.objects.create(
            staff=staff, start=now, end=now + datetime.timedelta(hours=1),
            name='佐藤', seat=self.seat, party_size=3,
        )
        self.client.login(username='tanakataro', password='helloworld123')
        response = self.client.get(resolve_url('booking:seat_board', pk=1))
        self.assertContains(response, 'T1')
        self.assertContains(response, '佐藤(3名)')

    def test_walkin_start_and_end(self):
        self.client.login(username='tanakataro', password='helloworld123')
        response = self.client.post(
            resolve_url('booking:walkin_start', seat_pk=self.seat.pk),
            {'party_size': '2'}, follow=True,
        )
        walkin = WalkIn.objects.get(seat=self.seat)
        self.assertTrue(walkin.is_active)
        self.assertEqual(walkin.party_size, 2)

        # 使用中の席には重ねて着席できない
        response = self.client.post(
            resolve_url('booking:walkin_start', seat_pk=self.seat.pk),
            {'party_size': '1'}, follow=True,
        )
        messages = [str(m) for m in response.context['messages']]
        self.assertIn('T1 は使用中です。', messages)

        self.client.post(resolve_url('booking:walkin_end', pk=walkin.pk))
        walkin.refresh_from_db()
        self.assertFalse(walkin.is_active)

    def test_seat_double_booking_rejected(self):
        staff1 = get_object_or_404(Staff, pk=1)
        staff3 = get_object_or_404(Staff, pk=3)
        now = timezone.localtime().replace(hour=10, minute=0, second=0, microsecond=0)
        Schedule.objects.create(
            staff=staff1, start=now, end=now + datetime.timedelta(hours=1), name='A', seat=self.seat,
        )
        with self.assertRaises(IntegrityError):
            Schedule.objects.create(
                staff=staff3, start=now, end=now + datetime.timedelta(hours=1), name='B', seat=self.seat,
            )

class ModelConstraintTests(TestCase):
    fixtures = ['initial']

    def test_store_rejects_overnight_hours(self):
        with self.assertRaises(IntegrityError):
            Store.objects.create(name='深夜バー', opening_hour=18, closing_hour=2)

    def test_store_allows_late_night_closing(self):
        store = Store.objects.create(name='26時閉店', opening_hour=18, closing_hour=26)
        self.assertEqual(list(store.business_hours), list(range(18, 26)))

    def test_store_rejects_hours_beyond_30(self):
        with self.assertRaises(IntegrityError):
            Store.objects.create(name='31時閉店', opening_hour=18, closing_hour=31)

    def test_store_rejects_span_over_24_hours(self):
        # 営業24時間超は翌日早朝の枠がどの営業日か曖昧になるため禁止
        with self.assertRaises(IntegrityError):
            Store.objects.create(name='ほぼ無休', opening_hour=1, closing_hour=26)

    def test_single_active_walkin_per_seat(self):
        store = Store.objects.get(pk=1)
        seat = Seat.objects.create(store=store, name='T9')
        WalkIn.objects.create(seat=seat, party_size=2)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                WalkIn.objects.create(seat=seat, party_size=1)
        # 離席後は再度着席できる
        active = WalkIn.objects.get(seat=seat)
        active.left_at = timezone.now()
        active.save()
        WalkIn.objects.create(seat=seat, party_size=3)
