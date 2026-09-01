import datetime

from django.shortcuts import resolve_url
from django.test import TestCase
from django.utils import timezone

from attendance.models import Shift
from booking.models import Staff, Store
from .models import BusinessDay, ChecklistTask, ChecklistTemplateItem
from . import services
from .signals import store_opened


class StartBusinessDayTests(TestCase):
    fixtures = ['initial']

    def setUp(self):
        self.store = Store.objects.get(pk=1)
        ChecklistTemplateItem.objects.create(store=self.store, title='清掃', order=1)
        ChecklistTemplateItem.objects.create(store=self.store, title='レジ開け・釣銭確認', order=2)
        ChecklistTemplateItem.objects.create(store=self.store, title='使わない項目', order=3, is_active=False)

    def test_creates_tasks_from_template(self):
        business_day = services.start_business_day(self.store, timezone.localdate())
        self.assertEqual(
            list(business_day.tasks.values_list('title', flat=True)),
            ['清掃', 'レジ開け・釣銭確認'],
        )

    def test_idempotent(self):
        services.start_business_day(self.store, timezone.localdate())
        business_day = services.start_business_day(self.store, timezone.localdate())
        self.assertEqual(business_day.tasks.count(), 2)
        self.assertEqual(BusinessDay.objects.filter(store=self.store).count(), 1)


class OpenStoreTests(TestCase):
    fixtures = ['initial']

    def setUp(self):
        self.store = Store.objects.get(pk=1)
        self.staff = Staff.objects.get(pk=1)
        self.today = timezone.localdate()

    def test_open_confirms_shifts_and_sets_status(self):
        shift = Shift.objects.create(
            staff=self.staff, date=self.today,
            start_time=datetime.time(18, 0), end_time=datetime.time(23, 0),
        )
        business_day = services.start_business_day(self.store, self.today)
        services.open_store(business_day)
        business_day.refresh_from_db()
        shift.refresh_from_db()
        self.assertEqual(business_day.status, BusinessDay.STATUS_OPEN)
        self.assertIsNotNone(business_day.opened_at)
        self.assertEqual(shift.status, Shift.STATUS_CONFIRMED)

    def test_failed_receiver_creates_alert_task(self):
        def failing_receiver(sender, business_day, **kwargs):
            raise RuntimeError('SNS投稿の生成に失敗')

        store_opened.connect(failing_receiver)
        try:
            business_day = services.start_business_day(self.store, self.today)
            services.open_store(business_day)
        finally:
            store_opened.disconnect(failing_receiver)

        alert_task = business_day.tasks.exclude(alert='').get()
        self.assertIn('SNS投稿の生成に失敗', alert_task.alert)
        # 自動処理が失敗しても開店自体は完了する
        business_day.refresh_from_db()
        self.assertEqual(business_day.status, BusinessDay.STATUS_OPEN)

    def test_open_twice_is_noop(self):
        business_day = services.start_business_day(self.store, self.today)
        services.open_store(business_day)
        opened_at = business_day.opened_at
        services.open_store(business_day)
        business_day.refresh_from_db()
        self.assertEqual(business_day.opened_at, opened_at)


class DashboardViewTests(TestCase):
    fixtures = ['initial']

    def test_requires_store_membership(self):
        # yosidaziro は店舗B(pk=2)のスタッフではない
        self.client.login(username='yosidaziro', password='helloworld123')
        response = self.client.get(resolve_url('operations:dashboard', store_pk=2))
        self.assertEqual(response.status_code, 403)

    def test_member_can_view(self):
        self.client.login(username='tanakataro', password='helloworld123')
        response = self.client.get(resolve_url('operations:dashboard', store_pk=1))
        self.assertContains(response, '開店ダッシュボード')

    def test_open_and_toggle_task(self):
        store = Store.objects.get(pk=1)
        ChecklistTemplateItem.objects.create(store=store, title='清掃', order=1)
        self.client.login(username='tanakataro', password='helloworld123')

        response = self.client.post(resolve_url('operations:open_store', store_pk=1), follow=True)
        self.assertContains(response, '開店しました')
        business_day = BusinessDay.objects.get(store=store, date=timezone.localdate())
        self.assertEqual(business_day.status, BusinessDay.STATUS_OPEN)

        task = business_day.tasks.get(title='清掃')
        self.client.post(resolve_url('operations:toggle_task', task_pk=task.pk))
        task.refresh_from_db()
        self.assertTrue(task.is_done)
        self.assertEqual(task.done_by.username, 'tanakataro')
