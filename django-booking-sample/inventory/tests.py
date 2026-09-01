import tempfile

from django.core import mail
from django.shortcuts import resolve_url
from django.test import TestCase, override_settings
from django.utils import timezone

from booking.models import Store
from operations import services as ops_services
from .models import Product, PurchaseOrder, StockMovement, Supplier
from . import services

MEDIA_TMP = tempfile.mkdtemp()


def make_product(store, name, supplier=None, reorder_point=0, stock=0, sns_announce=False, order_lot=1):
    product = Product.objects.create(
        store=store, name=name, supplier=supplier,
        reorder_point=reorder_point, sns_announce=sns_announce, order_lot=order_lot,
    )
    if stock:
        StockMovement.objects.create(product=product, kind=StockMovement.KIND_ARRIVAL, quantity=stock)
    return product


class StockTests(TestCase):
    fixtures = ['initial']

    def setUp(self):
        self.store = Store.objects.get(pk=1)

    def test_current_stock_sums_movements(self):
        product = make_product(self.store, '日本酒A', stock=10)
        StockMovement.objects.create(product=product, kind=StockMovement.KIND_SALE, quantity=-3)
        StockMovement.objects.create(product=product, kind=StockMovement.KIND_WASTE, quantity=-1)
        self.assertEqual(product.current_stock, 6)

    def test_sns_arrivals_only_flagged_products(self):
        make_product(self.store, '限定ワイン', sns_announce=True, stock=5)
        make_product(self.store, 'おしぼり', sns_announce=False, stock=100)
        arrivals = services.sns_arrivals(self.store, timezone.localdate())
        self.assertEqual(arrivals, ['限定ワイン'])

    def test_products_below_reorder_point(self):
        make_product(self.store, '在庫切れ', reorder_point=5, stock=3)
        make_product(self.store, '在庫十分', reorder_point=5, stock=30)
        names = [p.name for p in services.products_below_reorder_point(self.store)]
        self.assertEqual(names, ['在庫切れ'])


class OrderProposalTests(TestCase):
    fixtures = ['initial']

    def setUp(self):
        self.store = Store.objects.get(pk=1)
        self.supplier = Supplier.objects.create(store=self.store, name='酒販店X', email='order@example.com')

    def test_generates_proposal_grouped_by_supplier(self):
        supplier2 = Supplier.objects.create(store=self.store, name='卸Y')
        make_product(self.store, '日本酒A', supplier=self.supplier, reorder_point=5, stock=2, order_lot=12)
        make_product(self.store, '焼酎B', supplier=self.supplier, reorder_point=3, stock=0)
        make_product(self.store, 'グラスC', supplier=supplier2, reorder_point=10, stock=1)
        make_product(self.store, '在庫十分', supplier=self.supplier, reorder_point=1, stock=50)

        orders = services.generate_order_proposals(self.store)
        self.assertEqual(len(orders), 2)
        order_x = next(o for o in orders if o.supplier == self.supplier)
        items = {i.product.name: i.quantity for i in order_x.items.all()}
        self.assertEqual(items, {'日本酒A': 12, '焼酎B': 1})

    def test_no_duplicate_proposal_for_pending_products(self):
        make_product(self.store, '日本酒A', supplier=self.supplier, reorder_point=5, stock=2)
        first = services.generate_order_proposals(self.store)
        second = services.generate_order_proposals(self.store)
        self.assertEqual(len(first), 1)
        self.assertEqual(second, [])

    def test_supplierless_products_are_skipped(self):
        make_product(self.store, '仕入先なし', reorder_point=5, stock=0)
        self.assertEqual(services.generate_order_proposals(self.store), [])

    def test_approve_and_send_with_email(self):
        make_product(self.store, '日本酒A', supplier=self.supplier, reorder_point=5, stock=2)
        order = services.generate_order_proposals(self.store)[0]
        user = self.store.staff_set.first().user
        services.approve_and_send(order, user)
        order.refresh_from_db()
        self.assertEqual(order.status, PurchaseOrder.STATUS_SENT)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('日本酒A', mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].to, ['order@example.com'])

    def test_approve_without_email_marks_manual_note(self):
        supplier = Supplier.objects.create(store=self.store, name='FAXのみ卸')
        make_product(self.store, '氷', supplier=supplier, reorder_point=5, stock=0)
        order = services.generate_order_proposals(self.store)[0]
        user = self.store.staff_set.first().user
        services.approve_and_send(order, user)
        order.refresh_from_db()
        self.assertEqual(len(mail.outbox), 0)
        self.assertIn('送付してください', order.note)


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class OpenStoreInventoryIntegrationTests(TestCase):
    fixtures = ['initial']

    def setUp(self):
        self.store = Store.objects.get(pk=1)
        self.today = timezone.localdate()

    def test_restock_and_low_stock_tasks_created_on_open(self):
        supplier = Supplier.objects.create(store=self.store, name='酒販店X')
        make_product(self.store, '限定ワイン', supplier=supplier, sns_announce=True, stock=5)
        make_product(self.store, '日本酒A', supplier=supplier, reorder_point=5, stock=2)
        business_day = ops_services.start_business_day(self.store, self.today)
        ops_services.open_store(business_day)

        titles = list(business_day.tasks.values_list('title', flat=True))
        restock = next(t for t in titles if t.startswith('品出し(本日入荷)'))
        self.assertIn('限定ワイン', restock)
        self.assertIn('日本酒A', restock)
        self.assertTrue(any('日本酒A' in t and '発注案' in t for t in titles))

    def test_sns_body_includes_arrivals(self):
        make_product(self.store, '限定ワイン', sns_announce=True, stock=5)
        business_day = ops_services.start_business_day(self.store, self.today)
        ops_services.open_store(business_day)
        from sns.models import PostDraft
        draft = PostDraft.objects.get(store=self.store, date=self.today)
        self.assertIn('入荷情報: 限定ワイン', draft.body)


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class GbpReminderTests(TestCase):
    fixtures = ['initial']

    def test_reminder_only_when_hours_overridden(self):
        store = Store.objects.get(pk=1)
        today = timezone.localdate()

        business_day = ops_services.start_business_day(store, today)
        ops_services.open_store(business_day)
        self.assertFalse(business_day.tasks.filter(title__contains='Googleビジネスプロフィール').exists())

        business_day2 = ops_services.start_business_day(Store.objects.get(pk=2), today)
        business_day2.opening_hour_override = 12
        business_day2.save()
        ops_services.open_store(business_day2)
        self.assertTrue(
            business_day2.tasks.filter(title__contains='Googleビジネスプロフィール').exists()
        )


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class InventoryViewTests(TestCase):
    fixtures = ['initial']

    def setUp(self):
        self.store = Store.objects.get(pk=1)
        self.supplier = Supplier.objects.create(store=self.store, name='酒販店X', email='order@example.com')
        self.product = make_product(self.store, '日本酒A', supplier=self.supplier, reorder_point=5, stock=2)
        self.client.login(username='tanakataro', password='helloworld123')

    def test_stock_list_requires_membership(self):
        self.client.logout()
        self.client.login(username='yosidaziro', password='helloworld123')
        response = self.client.get(resolve_url('inventory:stock_list', store_pk=2))
        self.assertEqual(response.status_code, 403)

    def test_record_arrival(self):
        response = self.client.post(
            resolve_url('inventory:record_arrival', product_pk=self.product.pk),
            {'quantity': '10'}, follow=True,
        )
        self.assertContains(response, '入荷登録しました')
        self.assertEqual(self.product.current_stock, 12)

    def test_proposal_and_approve_flow(self):
        response = self.client.post(resolve_url('inventory:generate_proposals', store_pk=1), follow=True)
        self.assertContains(response, '発注案を生成しました')
        order = PurchaseOrder.objects.get(store=self.store)

        response = self.client.post(resolve_url('inventory:approve_order', pk=order.pk), follow=True)
        self.assertContains(response, '発注メールを送信しました')
        order.refresh_from_db()
        self.assertEqual(order.status, PurchaseOrder.STATUS_SENT)
        self.assertEqual(len(mail.outbox), 1)


class OrderLifecycleTests(TestCase):
    fixtures = ['initial']

    def setUp(self):
        self.store = Store.objects.get(pk=1)
        self.supplier = Supplier.objects.create(store=self.store, name='酒販店X')
        self.product = make_product(self.store, '日本酒A', supplier=self.supplier, reorder_point=5, stock=2, order_lot=6)
        self.user = self.store.staff_set.first().user

    def test_received_order_unblocks_future_proposals(self):
        order = services.generate_order_proposals(self.store)[0]
        services.approve_and_send(order, self.user)
        # 入荷待ちの間は再提案されない
        self.assertEqual(services.generate_order_proposals(self.store), [])
        # 入荷済みにすると在庫が増え、その後在庫が減ればまた提案される
        services.mark_received(order)
        order.refresh_from_db()
        self.assertEqual(order.status, PurchaseOrder.STATUS_RECEIVED)
        self.assertEqual(self.product.current_stock, 8)  # 2 + 発注ロット6
        StockMovement.objects.create(product=self.product, kind=StockMovement.KIND_SALE, quantity=-7)
        self.assertEqual(len(services.generate_order_proposals(self.store)), 1)

    def test_stale_sent_order_stops_blocking_after_30_days(self):
        import datetime as dt
        from django.utils import timezone as tz
        order = services.generate_order_proposals(self.store)[0]
        services.approve_and_send(order, self.user)
        # 送信から30日経過(入荷済みへの更新を忘れたケース)
        PurchaseOrder.objects.filter(pk=order.pk).update(
            sent_at=tz.now() - dt.timedelta(days=31)
        )
        proposals = services.generate_order_proposals(self.store)
        self.assertEqual(len(proposals), 1)

    def test_receive_order_view(self):
        order = services.generate_order_proposals(self.store)[0]
        services.approve_and_send(order, self.user)
        self.client.login(username='tanakataro', password='helloworld123')
        response = self.client.post(resolve_url('inventory:receive_order', pk=order.pk), follow=True)
        self.assertContains(response, '入荷済みにし')
        order.refresh_from_db()
        self.assertEqual(order.status, PurchaseOrder.STATUS_RECEIVED)
