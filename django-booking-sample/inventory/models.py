from django.conf import settings
from django.db import models
from django.utils import timezone

from booking.models import Store


class Supplier(models.Model):
    """仕入先。メールアドレスがあれば発注書を自動送信、なければ手動送付用テキストを出力。"""
    store = models.ForeignKey(Store, verbose_name='店舗', on_delete=models.CASCADE, related_name='suppliers')
    name = models.CharField('仕入先名', max_length=100)
    email = models.EmailField('発注先メール', blank=True)
    note = models.CharField('メモ(電話番号・FAX等)', max_length=255, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.store.name} - {self.name}'


class Product(models.Model):
    """商品マスタ"""
    store = models.ForeignKey(Store, verbose_name='店舗', on_delete=models.CASCADE, related_name='products')
    name = models.CharField('品名', max_length=100)
    category = models.CharField('カテゴリ', max_length=50, blank=True)
    supplier = models.ForeignKey(
        Supplier, verbose_name='仕入先', on_delete=models.SET_NULL, null=True, blank=True, related_name='products'
    )
    unit = models.CharField('単位', max_length=20, default='個')
    reorder_point = models.PositiveIntegerField('発注点', default=0)
    order_lot = models.PositiveIntegerField('発注ロット', default=1)
    # SNSの入荷告知に載せてよい商品か
    sns_announce = models.BooleanField('SNS告知対象', default=False)
    is_active = models.BooleanField('取扱中', default=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['store', 'name'], name='unique_product_per_store'),
        ]

    def __str__(self):
        return f'{self.store.name} - {self.name}'

    @property
    def current_stock(self):
        return self.movements.aggregate(total=models.Sum('quantity'))['total'] or 0

    @property
    def is_below_reorder_point(self):
        return self.current_stock <= self.reorder_point


class StockMovement(models.Model):
    """入出庫記録。入荷は正、消費・廃棄は負の数量で記録する。棚卸補正も差分で記録。"""
    KIND_ARRIVAL = 'arrival'
    KIND_SALE = 'sale'
    KIND_WASTE = 'waste'
    KIND_ADJUST = 'adjust'
    KIND_CHOICES = [
        (KIND_ARRIVAL, '入荷'),
        (KIND_SALE, '販売・消費'),
        (KIND_WASTE, '廃棄'),
        (KIND_ADJUST, '棚卸補正'),
    ]

    product = models.ForeignKey(Product, verbose_name='商品', on_delete=models.CASCADE, related_name='movements')
    kind = models.CharField('種別', max_length=10, choices=KIND_CHOICES)
    quantity = models.IntegerField('数量(入荷は正、消費は負)')
    at = models.DateTimeField('日時', default=timezone.now)
    note = models.CharField('メモ', max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='記録者', on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        ordering = ['-at']

    def __str__(self):
        return f'{self.product.name} {self.get_kind_display()} {self.quantity:+d}'


class PurchaseOrder(models.Model):
    """発注。自動生成されるのは「発注案(proposed)」まで。送信は人間の承認後(要件F-4)。"""
    STATUS_PROPOSED = 'proposed'
    STATUS_SENT = 'sent'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_PROPOSED, '発注案(承認待ち)'),
        (STATUS_SENT, '発注済み'),
        (STATUS_CANCELLED, '取消'),
    ]

    store = models.ForeignKey(Store, verbose_name='店舗', on_delete=models.CASCADE, related_name='purchase_orders')
    supplier = models.ForeignKey(Supplier, verbose_name='仕入先', on_delete=models.CASCADE, related_name='purchase_orders')
    status = models.CharField('状態', max_length=10, choices=STATUS_CHOICES, default=STATUS_PROPOSED)
    created_at = models.DateTimeField('作成', auto_now_add=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='承認者', on_delete=models.SET_NULL, null=True, blank=True
    )
    sent_at = models.DateTimeField('送信時刻', null=True, blank=True)
    note = models.CharField('メモ', max_length=255, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.supplier.name} 宛 ({self.get_status_display()})'

    def as_text(self):
        """メール本文・FAX/LINE用の発注書テキスト。"""
        lines = [
            f'{self.supplier.name} 御中',
            '',
            f'{self.store.name} です。以下の通り発注いたします。',
            '',
        ]
        for item in self.items.select_related('product'):
            lines.append(f'・{item.product.name} × {item.quantity}{item.product.unit}')
        lines += ['', 'よろしくお願いいたします。', self.store.name]
        return '\n'.join(lines)


class PurchaseOrderItem(models.Model):
    order = models.ForeignKey(PurchaseOrder, verbose_name='発注', on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, verbose_name='商品', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField('数量')

    def __str__(self):
        return f'{self.product.name} × {self.quantity}'
