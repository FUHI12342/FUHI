import datetime

from django.shortcuts import resolve_url
from django.test import TestCase
from django.utils import timezone

from booking.models import Staff, Store
from .models import Shift, TimeRecord, confirm_shifts


def create_shift(staff, date, status=Shift.STATUS_PLANNED, start=datetime.time(18, 0), end=datetime.time(23, 0)):
    return Shift.objects.create(staff=staff, date=date, start_time=start, end_time=end, status=status)


class ShiftQuerySetTests(TestCase):
    fixtures = ['initial']

    def setUp(self):
        self.store = Store.objects.get(pk=1)
        self.staff1 = Staff.objects.get(pk=1)  # 店舗A ぱいそん
        self.staff3 = Staff.objects.get(pk=3)  # 店舗A じゃば
        self.today = timezone.localdate()

    def test_on_duty_excludes_absent(self):
        create_shift(self.staff1, self.today)
        create_shift(self.staff3, self.today, status=Shift.STATUS_ABSENT)
        shifts = Shift.objects.on_duty(self.store, self.today)
        self.assertEqual([s.staff for s in shifts], [self.staff1])

    def test_publishable_casts_filters_flags(self):
        # SNS掲載可・在籍中のみが対象になる
        self.staff1.sns_publishable = True
        self.staff1.save()
        self.staff3.sns_publishable = True
        self.staff3.is_on_roster = False  # 退職済み
        self.staff3.save()
        create_shift(self.staff1, self.today)
        create_shift(self.staff3, self.today)
        shifts = Shift.objects.publishable_casts(self.store, self.today)
        self.assertEqual([s.staff for s in shifts], [self.staff1])

    def test_confirm_shifts(self):
        s1 = create_shift(self.staff1, self.today)
        s2 = create_shift(self.staff3, self.today, status=Shift.STATUS_ABSENT)
        updated = confirm_shifts(self.store, self.today)
        self.assertEqual(updated, 1)
        s1.refresh_from_db()
        s2.refresh_from_db()
        self.assertEqual(s1.status, Shift.STATUS_CONFIRMED)
        self.assertEqual(s2.status, Shift.STATUS_ABSENT)


class ClockViewTests(TestCase):
    fixtures = ['initial']

    def setUp(self):
        self.client.login(username='tanakataro', password='helloworld123')
        self.staff1 = Staff.objects.get(pk=1)  # tanakataro の店舗Aスタッフ

    def test_clock_in_and_out(self):
        response = self.client.post(resolve_url('attendance:clock_in', staff_pk=1), follow=True)
        self.assertEqual(response.status_code, 200)
        record = TimeRecord.objects.get(staff=self.staff1, date=timezone.localdate())
        self.assertIsNotNone(record.clock_in)
        self.assertIsNone(record.clock_out)

        response = self.client.post(resolve_url('attendance:clock_out', staff_pk=1), follow=True)
        record.refresh_from_db()
        self.assertIsNotNone(record.clock_out)
        self.assertIsNotNone(record.worked_minutes)

    def test_clock_out_without_clock_in(self):
        response = self.client.post(resolve_url('attendance:clock_out', staff_pk=1), follow=True)
        messages = [str(m) for m in response.context['messages']]
        self.assertIn('出勤打刻がありません。', messages)

    def test_cannot_clock_other_users_staff(self):
        # staff pk=3 は yosidaziro のもの
        response = self.client.post(resolve_url('attendance:clock_in', staff_pk=3))
        self.assertEqual(response.status_code, 403)

    def test_my_attendance_page(self):
        response = self.client.get(resolve_url('attendance:my_attendance'))
        self.assertContains(response, '勤怠')


class MonthlyCsvExportTests(TestCase):
    fixtures = ['initial']

    def test_requires_superuser(self):
        self.client.login(username='tanakataro', password='helloworld123')
        today = timezone.localdate()
        response = self.client.get(resolve_url('attendance:monthly_csv', store_pk=1, year=today.year, month=today.month))
        self.assertEqual(response.status_code, 403)

    def test_csv_content(self):
        staff = Staff.objects.get(pk=1)
        today = timezone.localdate()
        create_shift(staff, today, status=Shift.STATUS_CONFIRMED)
        clock_in = timezone.now().replace(hour=18, minute=0, second=0, microsecond=0)
        TimeRecord.objects.create(staff=staff, date=today, clock_in=clock_in, clock_out=clock_in + datetime.timedelta(hours=5))
        self.client.login(username='admin', password='admin123')
        response = self.client.get(resolve_url('attendance:monthly_csv', store_pk=1, year=today.year, month=today.month))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8')
        self.assertIn('ぱいそん', body)
        self.assertIn('300', body)  # 実働300分
