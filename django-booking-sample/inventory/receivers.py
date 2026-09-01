from django.dispatch import receiver

from operations.models import ChecklistTask
from operations.signals import store_opened

from . import services


@receiver(store_opened, dispatch_uid='inventory_restock_tasks_on_open')
def create_restock_tasks_on_open(sender, business_day, user=None, **kwargs):
    """開店時に品出し・発注確認タスクをチェックリストへ反映する(要件F-3)。"""
    store = business_day.store

    arrived = services.arrived_product_names(store, business_day.date)
    if arrived:
        ChecklistTask.objects.get_or_create(
            business_day=business_day,
            # title は max_length=200。商品名が多い日でも超過しないよう切り詰める
            title=f"品出し(本日入荷): {'、'.join(arrived[:10])}"[:200],
            defaults={'order': 910},
        )

    low = services.products_below_reorder_point(store)
    if low:
        names = '、'.join(p.name for p in low[:10])
        ChecklistTask.objects.get_or_create(
            business_day=business_day,
            title=f'在庫僅少を確認し発注案を承認する: {names}'[:200],
            defaults={'order': 920},
        )
