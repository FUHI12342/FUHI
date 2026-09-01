import datetime

from django.shortcuts import get_object_or_404
from django.shortcuts import resolve_url
from django.test import TestCase
from django.utils import timezone

from booking.models import Schedule, Staff
from booking.tests import batu, line, maru


class StoreListViewTests(TestCase):
    fixtures = ['initial']

    def test_get(self):
        """店舗の一覧が表示されるかテスト"""
        response = self.client.get(resolve_url('booking:store_list'))
        self.assertQuerySetEqual(response.context['store_list'], ['店舗A', '店舗B', '店舗C'], transform=str)

class StaffListViewTests(TestCase):
    fixtures = ['initial']

    def test_store_a(self):
        """店舗Aのスタッフリストの確認"""
        response = self.client.get(resolve_url('booking:staff_list', pk=1))
        self.assertQuerySetEqual(response.context['staff_list'], ['店舗A - じゃば', '店舗A - ぱいそん'], transform=str)

    def test_store_b(self):
        """店舗Bのスタッフリストの確認"""
        response = self.client.get(resolve_url('booking:staff_list', pk=2))
        self.assertQuerySetEqual(response.context['staff_list'], ['店舗B - じゃんご'], transform=str)

    def test_store_c(self):
        """店舗Cのスタッフリストの確認。店舗Cには誰もいない"""
        response = self.client.get(resolve_url('booking:staff_list', pk=3))
        self.assertQuerySetEqual(response.context['staff_list'], [])

class StaffCalendarViewTests(TestCase):
    fixtures = ['initial']

    def test_no_schedule(self):
        """スケジュールがない場合のカレンダーをテスト。

        店名や表示期間と、「☓」がないことを確認。これがあるのはスケジュールがある場合。
        """
        start = timezone.localtime()
        end = start + datetime.timedelta(days=6)
        response = self.client.get(resolve_url('booking:calendar', pk=1))
        self.assertContains(response, '店舗A店 ぱいそん')
        self.assertContains(response, f'{start.year}年{start.month}月{start.day}日 - {end.year}年{end.month}月{end.day}日')
        self.assertContains(response, line)
        self.assertContains(response, maru)
        self.assertNotContains(response, batu)

    def test_one_schedule_next_day_9(self):
        """スケジュールが次の日の9時

        スケジュールがあるので、☓がカレンダー内に表示されることを確認
        """
        staff = get_object_or_404(Staff, pk=1)
        start = timezone.localtime() + datetime.timedelta(days=1)
        start = start.replace(hour=9, minute=0, second=0)
        end = start + datetime.timedelta(hours=1)
        Schedule.objects.create(staff=staff, start=start, end=end, name='テスト')
        response = self.client.get(resolve_url('booking:calendar', pk=staff.pk))
        self.assertContains(response, line)
        self.assertContains(response, maru)
        self.assertContains(response, batu)

    def test_one_schedule_next_day_8(self):
        """スケジュールが次の日の8時

        8時のスケジュールはカレンダーに表示されないので、☓がないことを確認
        """
        staff = get_object_or_404(Staff, pk=1)
        start = timezone.localtime() + datetime.timedelta(days=1)
        start = start.replace(hour=8, minute=0, second=0)
        end = start + datetime.timedelta(hours=1)
        Schedule.objects.create(staff=staff, start=start, end=end, name='テスト')
        response = self.client.get(resolve_url('booking:calendar', pk=staff.pk))
        self.assertContains(response, line)
        self.assertContains(response, maru)
        self.assertNotContains(response, batu)

    def test_one_schedule_next_day_17(self):
        """スケジュールが次の日の17時

        17時はカレンダーに表示されるので、☓があることを確認
        """
        staff = get_object_or_404(Staff, pk=1)
        start = timezone.localtime() + datetime.timedelta(days=1)
        start = start.replace(hour=17, minute=0, second=0)
        end = start + datetime.timedelta(hours=1)
        Schedule.objects.create(staff=staff, start=start, end=end, name='テスト')
        response = self.client.get(resolve_url('booking:calendar', pk=staff.pk))
        self.assertContains(response, line)
        self.assertContains(response, maru)
        self.assertContains(response, batu)

    def test_one_schedule_next_day_18(self):
        """次の日の18時にスケジュール

        18時はカレンダー表示されないので、☓がないことを確認
        """
        staff = get_object_or_404(Staff, pk=1)
        start = timezone.localtime() + datetime.timedelta(days=1)
        start = start.replace(hour=18, minute=0, second=0)
        end = start + datetime.timedelta(hours=1)
        Schedule.objects.create(staff=staff, start=start, end=end, name='テスト')
        response = self.client.get(resolve_url('booking:calendar', pk=staff.pk))
        self.assertContains(response, line)
        self.assertContains(response, maru)
        self.assertNotContains(response, batu)

    def test_one_schedule_before_day_9(self):
        """前の日の9時にスケジュール

        カレンダーは当日から表示なので、前の日のものは表示されない。☓がないことを確認。
        """
        staff = get_object_or_404(Staff, pk=1)
        start = timezone.localtime() - datetime.timedelta(days=1)
        start = start.replace(hour=9, minute=0, second=0)
        end = start + datetime.timedelta(hours=1)
        Schedule.objects.create(staff=staff, start=start, end=end, name='テスト')
        response = self.client.get(resolve_url('booking:calendar', pk=staff.pk))
        self.assertContains(response, line)
        self.assertContains(response, maru)
        self.assertNotContains(response, batu)

    def test_one_schedule_next_week_9(self):
        """来週の9時にスケジュール

        7日後は表示されない。☓がないことを確認
        """
        staff = get_object_or_404(Staff, pk=1)
        start = timezone.localtime() + datetime.timedelta(days=7)
        start = start.replace(hour=9, minute=0, second=0)
        end = start + datetime.timedelta(hours=1)
        Schedule.objects.create(staff=staff, start=start, end=end, name='テスト')
        response = self.client.get(resolve_url('booking:calendar', pk=staff.pk))
        self.assertContains(response, line)
        self.assertContains(response, maru)
        self.assertNotContains(response, batu)

    def test_one_schedule_next_week_9_and_move(self):
        """来週の9時にスケジュール

        7日後を基準にカレンダー表示するので、スケジュールは表示される。☓があることを確認。
        """
        staff = get_object_or_404(Staff, pk=1)
        start = timezone.localtime() + datetime.timedelta(days=7)
        start = start.replace(hour=9, minute=0, second=0)
        end = start + datetime.timedelta(hours=1)
        Schedule.objects.create(staff=staff, start=start, end=end, name='テスト')
        response = self.client.get(resolve_url('booking:calendar', pk=staff.pk, year=start.year, month=start.month, day=start.day))
        self.assertContains(response, line)
        self.assertContains(response, maru)
        self.assertContains(response, batu)

        end = start + datetime.timedelta(days=6)
        self.assertContains(response, '店舗A店 ぱいそん')
        self.assertContains(response, f'{start.year}年{start.month}月{start.day}日 - {end.year}年{end.month}月{end.day}日')

class BookingViewTests(TestCase):
    fixtures = ['initial']

    def test_get(self):
        """予約ページが表示されるかテスト"""
        now = timezone.localtime()
        response = self.client.get(resolve_url('booking:booking', pk=1, year=now.year, month=now.month, day=now.day, hour=9))
        self.assertContains(response, '店舗A店 ぱいそん')
        self.assertContains(response, f'{now.year}年{now.month}月{now.day}日 9時に予約')

    def test_post(self):
        """予約後に、カレンダーページで☓（予約あり）があることを確認"""
        now = timezone.localtime() + datetime.timedelta(days=1)
        response = self.client.post(
            resolve_url('booking:booking', pk=1, year=now.year, month=now.month, day=now.day, hour=9),
            {'name': 'テスト'},
            follow=True
        )
        messages = list(response.context['messages'])
        self.assertEqual(messages, [])
        self.assertContains(response, batu)

    def test_post_exists_data(self):
        """既に埋まった時間に予約した場合に、メッセージ表示があることを確認"""
        now = timezone.localtime().replace(hour=9, minute=0, second=0, microsecond=0)
        end = now + datetime.timedelta(hours=1)
        staff = get_object_or_404(Staff, pk=1)
        Schedule.objects.create(staff=staff, start=now, end=end, name='埋めた')
        response = self.client.post(
            resolve_url('booking:booking', pk=1, year=now.year, month=now.month, day=now.day, hour=9),
            {'name': 'これは入らない'},
            follow=True
        )
        messages = list(response.context['messages'])
        self.assertEqual(str(messages[0]), 'すみません、入れ違いで予約がありました。別の日時はどうですか。')
