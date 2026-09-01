import datetime
import logging

from django.core.mail import send_mail
from django.db import models
from django.utils import timezone

from .models import Product, PurchaseOrder, PurchaseOrderItem, StockMovement

logger = logging.getLogger(__name__)


def sns_arrivals(store, date):
    """SNS告知対象の商品のうち、指定日に入荷したものの品名リスト(SNS文面の差し込み用)。"""
    tz = timezone.get_current_timezone()
    day_start = datetime.datetime.combine(date, datetime.time.min, tzinfo=tz)
    day_end = day_start + datetime.timedelta(days=1)
    names = (
        StockMovement.objects.filter(
            product__store=store,
            product__sns_announce=True,
            product__is_active=True,
            kind=StockMovement.KIND_ARRIVAL,
            at__gte=day_start,
            at__lt=day_end,
        )
        .values_list('product__name', flat=True)
        .distinct()
    )
    return list(names)


def arrived_product_names(store, date):
    """指定日に入荷した全商品名(品出しタスク用。SNS告知フラグは問わない)。"""
    tz = timezone.get_current_timezone()
    day_start = datetime.datetime.combine(date, datetime.time.min, tzinfo=tz)
    day_end = day_start + datetime.timedelta(days=1)
    return list(
        StockMovement.objects.filter(
            product__store=store, kind=StockMovement.KIND_ARRIVAL,
            at__gte=day_start, at__lt=day_end,
        ).values_list('product__name', flat=True).distinct()
    )


def products_below_reorder_point(store):
    """発注点を下回った(現在庫 <= 発注点)取扱中の商品。"""
    products = (
        Product.objects.filter(store=store, is_active=True)
        .annotate(stock=models.functions.Coalesce(models.Sum('movements__quantity'), 0))
        .filter(stock__lte=models.F('reorder_point'))
    )
    return list(products)


# 「発注済み(入荷待ち)」が再提案をブロックする期間。入荷済みへの更新を忘れても、
# この日数を過ぎれば再提案が復活する(商品が永久にブロックされる事故の防止)。
SENT_ORDER_BLOCK_DAYS = 30


def generate_order_proposals(store):
    """発注点割れの商品から、仕入先ごとの発注案を生成する。

    - 送信はしない。人間の承認(approve_and_send)が必須(要件F-4、完全自動発注は見送り)。
    - 発注案(承認待ち)と、送信後30日以内の「入荷待ち」に載っている商品は重複提案しない。
      入荷登録時に発注を「入荷済み」へ更新すればその時点でブロックが外れる。
    """
    sent_cutoff = timezone.now() - datetime.timedelta(days=SENT_ORDER_BLOCK_DAYS)
    pending_product_ids = set(
        PurchaseOrderItem.objects.filter(
            models.Q(order__status=PurchaseOrder.STATUS_PROPOSED)
            | models.Q(order__status=PurchaseOrder.STATUS_SENT, order__sent_at__gte=sent_cutoff),
            order__store=store,
        ).values_list('product_id', flat=True)
    )

    by_supplier = {}
    for product in products_below_reorder_point(store):
        if product.pk in pending_product_ids or product.supplier is None:
            continue
        by_supplier.setdefault(product.supplier, []).append(product)

    orders = []
    for supplier, products in by_supplier.items():
        order = PurchaseOrder.objects.create(store=store, supplier=supplier)
        PurchaseOrderItem.objects.bulk_create([
            PurchaseOrderItem(order=order, product=p, quantity=max(p.order_lot, 1))
            for p in products
        ])
        orders.append(order)
    return orders


def approve_and_send(order, user):
    """発注案を承認し、仕入先へ送信する。

    - メールアドレスがあれば発注書メールを送信して「発注済み」。
    - なければ「発注済み」にしたうえで、発注書テキストを電話/FAX/LINEで手動送付する旨を注記。
    """
    order.approved_by = user
    if order.supplier.email:
        send_mail(
            subject=f'【発注】{order.store.name}',
            message=order.as_text(),
            from_email=None,  # DEFAULT_FROM_EMAIL
            recipient_list=[order.supplier.email],
        )
        order.note = ''
    else:
        order.note = 'メール未設定のため、発注書テキストを電話/FAX/LINEで送付してください。'
    order.status = PurchaseOrder.STATUS_SENT
    order.sent_at = timezone.now()
    order.save(update_fields=['status', 'approved_by', 'sent_at', 'note'])
    return order


def mark_received(order, record_stock=True):
    """発注を「入荷済み」にし、任意で発注数量ぶんの入荷を在庫に記録する。"""
    if order.status != PurchaseOrder.STATUS_SENT:
        return order
    if record_stock:
        StockMovement.objects.bulk_create([
            StockMovement(
                product=item.product, kind=StockMovement.KIND_ARRIVAL,
                quantity=item.quantity, note=f'発注 #{order.pk} の入荷',
            )
            for item in order.items.select_related('product')
        ])
    order.status = PurchaseOrder.STATUS_RECEIVED
    order.save(update_fields=['status'])
    return order
