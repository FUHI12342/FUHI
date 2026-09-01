import tempfile

from django.shortcuts import resolve_url
from django.test import TestCase
from django.test import override_settings
from django.utils import timezone

from booking.models import Store
from inventory.models import Product, StockMovement
from operations import services as ops
from sns import services as sns_services
from sns.models import PostDraft


class ManagerRoleTests(TestCase):
    """承認系操作は店長(is_manager)限定であることの確認。

    fixture: tanakataro のスタッフ(pk=1,2)は店長、yosidaziro のスタッフ(pk=3)は一般。
    """
    fixtures = ['initial']

    def test_non_manager_cannot_open_store(self):
        self.client.login(username='yosidaziro', password='helloworld123')
        response = self.client.post(resolve_url('operations:open_store', store_pk=1))
        self.assertEqual(response.status_code, 403)

    def test_manager_can_open_store(self):
        self.client.login(username='tanakataro', password='helloworld123')
        response = self.client.post(resolve_url('operations:open_store', store_pk=1), follow=True)
        self.assertEqual(response.status_code, 200)

    def test_non_manager_cannot_approve_sns_draft(self):
        with override_settings(MEDIA_ROOT=tempfile.mkdtemp()):
            draft = sns_services.generate_draft(Store.objects.get(pk=1), timezone.localdate())
        self.client.login(username='yosidaziro', password='helloworld123')
        response = self.client.post(resolve_url('sns:approve', pk=draft.pk))
        self.assertEqual(response.status_code, 403)

    def test_non_manager_can_still_view_dashboard_and_toggle_tasks(self):
        # 一般スタッフ(キャスト)もダッシュボード閲覧とチェックリスト操作はできる
        self.client.login(username='yosidaziro', password='helloworld123')
        response = self.client.get(resolve_url('operations:dashboard', store_pk=1))
        self.assertEqual(response.status_code, 200)

class FeatureFlagTests(TestCase):
    """店舗ごとの機能フラグ。オフの機能は404になり、開店連鎖からも除外される。"""
    fixtures = ['initial']

    def setUp(self):
        self.store = Store.objects.get(pk=1)
        self.client.login(username='tanakataro', password='helloworld123')

    def _open_store(self):
        with override_settings(MEDIA_ROOT=tempfile.mkdtemp()):
            business_day = ops.start_business_day(self.store, timezone.localdate())
            ops.open_store(business_day)
        return business_day

    def test_sns_disabled_hides_views_and_skips_generation(self):
        self.store.enable_sns = False
        self.store.save()
        response = self.client.get(resolve_url('sns:draft_list', store_pk=1))
        self.assertEqual(response.status_code, 404)

        business_day = self._open_store()
        self.assertFalse(PostDraft.objects.filter(store=self.store).exists())
        self.assertFalse(business_day.tasks.filter(title__contains='SNS').exists())
        # 開店自体は成功している
        self.assertEqual(business_day.status, 'open')

    def test_inventory_disabled_hides_views_and_skips_tasks(self):
        self.store.enable_inventory = False
        self.store.save()
        response = self.client.get(resolve_url('inventory:stock_list', store_pk=1))
        self.assertEqual(response.status_code, 404)

        product = Product.objects.create(store=self.store, name='入荷品', reorder_point=5)
        StockMovement.objects.create(product=product, kind=StockMovement.KIND_ARRIVAL, quantity=3)
        business_day = self._open_store()
        self.assertFalse(business_day.tasks.filter(title__contains='品出し').exists())
        self.assertFalse(business_day.tasks.filter(title__contains='発注案').exists())

    def test_seat_board_disabled_returns_404(self):
        self.store.enable_seat_board = False
        self.store.save()
        response = self.client.get(resolve_url('booking:seat_board', pk=1))
        self.assertEqual(response.status_code, 404)

    def test_gbp_disabled_skips_reminder(self):
        self.store.enable_gbp = False
        self.store.save()
        with override_settings(MEDIA_ROOT=tempfile.mkdtemp()):
            business_day = ops.start_business_day(self.store, timezone.localdate())
            business_day.opening_hour_override = 12
            business_day.save()
            ops.open_store(business_day)
        self.assertFalse(business_day.tasks.filter(title__contains='Googleビジネスプロフィール').exists())

    def test_flags_default_on(self):
        # デフォルトは全機能ON(既存店舗の挙動を変えない)
        store = Store.objects.create(name='新店', opening_hour=10, closing_hour=20)
        self.assertTrue(store.enable_sns)
        self.assertTrue(store.enable_inventory)
        self.assertTrue(store.enable_seat_board)
        self.assertTrue(store.enable_gbp)
