"""デモデータ投入コマンド。開店ダッシュボード〜SNS承認〜発注までの一連の流れを
すぐ試せる状態を作る。開発用のため DEBUG=True でのみ実行可能。

    python manage.py seed_demo
"""
import datetime

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from attendance.models import Shift
from booking.models import Seat, Staff, Store
from inventory.models import Product, StockMovement, Supplier
from operations.models import ChecklistTemplateItem

DEMO_PASSWORD = 'demo12345'


class Command(BaseCommand):
    help = 'デモ用の店舗・キャスト・座席・商品・シフト・チェックリスト雛形を投入する(DEBUG時のみ)'

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('本番環境(DEBUG=False)では実行できません。')

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username='demo', defaults={'is_staff': True, 'is_superuser': True}
        )
        if created:
            user.set_password(DEMO_PASSWORD)
            user.save()

        store, _ = Store.objects.get_or_create(
            name='デモ店舗', defaults={
                'business_type': Store.TYPE_RESTAURANT,
                'opening_hour': 18, 'closing_hour': 26,  # 18時-翌2時(深夜営業)
            }
        )

        manager, _ = Staff.objects.get_or_create(
            user=user, store=store,
            defaults={'name': '店長', 'kind': Staff.KIND_STAFF, 'is_manager': True},
        )

        cast_names = ['あかり', 'みお', 'ゆず']
        casts = []
        for i, name in enumerate(cast_names):
            cast_user, created = User.objects.get_or_create(username=f'cast{i + 1}')
            if created:
                cast_user.set_password(DEMO_PASSWORD)
                cast_user.save()
            cast, _ = Staff.objects.get_or_create(
                user=cast_user, store=store,
                defaults={'name': name, 'kind': Staff.KIND_CAST, 'sns_publishable': i < 2},
            )
            casts.append(cast)

        today = timezone.localdate()
        for cast in casts[:2]:
            Shift.objects.get_or_create(
                staff=cast, date=today, start_time=datetime.time(19, 0),
                defaults={'end_time': datetime.time(23, 0)},
            )

        for name, seat_type, capacity in [
            ('C1', Seat.TYPE_COUNTER, 1), ('C2', Seat.TYPE_COUNTER, 1),
            ('T1', Seat.TYPE_TABLE, 4), ('V1', Seat.TYPE_PRIVATE, 6),
        ]:
            Seat.objects.get_or_create(store=store, name=name, defaults={'seat_type': seat_type, 'capacity': capacity})

        for order, title in enumerate(['店内清掃', 'レジ開け・釣銭確認', '看板・外灯を出す', 'ドリンクの品出し'], start=1):
            ChecklistTemplateItem.objects.get_or_create(store=store, title=title, defaults={'order': order})

        supplier, _ = Supplier.objects.get_or_create(store=store, name='デモ酒販店', defaults={'email': ''})
        wine, _ = Product.objects.get_or_create(
            store=store, name='限定ワイン', defaults={
                'supplier': supplier, 'reorder_point': 2, 'order_lot': 6, 'sns_announce': True, 'unit': '本',
            }
        )
        beer, _ = Product.objects.get_or_create(
            store=store, name='瓶ビール', defaults={
                'supplier': supplier, 'reorder_point': 12, 'order_lot': 24, 'unit': '本',
            }
        )
        if not wine.movements.exists():
            StockMovement.objects.create(product=wine, kind=StockMovement.KIND_ARRIVAL, quantity=6)
        if not beer.movements.exists():
            StockMovement.objects.create(product=beer, kind=StockMovement.KIND_ARRIVAL, quantity=6)  # 発注点割れの状態

        self.stdout.write(self.style.SUCCESS(
            f'デモデータを投入しました。\n'
            f'  ログイン: demo / {DEMO_PASSWORD}\n'
            f'  開店ダッシュボード: /ops/store/{store.pk}/today/\n'
            f'  座席ボード: /store/{store.pk}/seats/\n'
            f'  Web座席予約(顧客向け): /store/{store.pk}/reserve/\n'
            f'  SNS投稿: /sns/store/{store.pk}/drafts/\n'
            f'  在庫・発注: /inventory/store/{store.pk}/'
        ))
