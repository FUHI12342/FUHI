from django.conf import settings
from django.db import models
from django.utils import timezone

from booking.models import Store


class BusinessDay(models.Model):
    """営業日。開店業務自動化のハブとなるエンティティ。"""
    STATUS_PREPARING = 'preparing'
    STATUS_OPEN = 'open'
    STATUS_CLOSED = 'closed'
    STATUS_CHOICES = [
        (STATUS_PREPARING, '準備中'),
        (STATUS_OPEN, '営業中'),
        (STATUS_CLOSED, '閉店'),
    ]

    store = models.ForeignKey(Store, verbose_name='店舗', on_delete=models.CASCADE, related_name='business_days')
    date = models.DateField('日付')
    status = models.CharField('状態', max_length=10, choices=STATUS_CHOICES, default=STATUS_PREPARING)
    # 臨時の営業時間変更(空なら店舗のデフォルト)
    opening_hour_override = models.PositiveSmallIntegerField('臨時開店時刻(時)', null=True, blank=True)
    closing_hour_override = models.PositiveSmallIntegerField('臨時閉店時刻(時)', null=True, blank=True)
    opened_at = models.DateTimeField('開店時刻', null=True, blank=True)
    closed_at = models.DateTimeField('閉店時刻', null=True, blank=True)
    note = models.CharField('メモ', max_length=255, blank=True)

    class Meta:
        ordering = ['-date']
        constraints = [
            models.UniqueConstraint(fields=['store', 'date'], name='unique_business_day'),
        ]

    def __str__(self):
        return f'{self.store.name} {self.date} ({self.get_status_display()})'

    @property
    def opening_hour(self):
        return self.opening_hour_override if self.opening_hour_override is not None else self.store.opening_hour

    @property
    def closing_hour(self):
        return self.closing_hour_override if self.closing_hour_override is not None else self.store.closing_hour


class ChecklistTemplateItem(models.Model):
    """開店チェックリストの雛形(店舗ごと)。"""
    store = models.ForeignKey(Store, verbose_name='店舗', on_delete=models.CASCADE, related_name='checklist_template')
    title = models.CharField('タスク名', max_length=100)
    order = models.PositiveSmallIntegerField('表示順', default=0)
    is_active = models.BooleanField('有効', default=True)

    class Meta:
        ordering = ['order', 'pk']

    def __str__(self):
        return f'{self.store.name}: {self.title}'


class ChecklistTask(models.Model):
    """当日の開店チェックリストのタスク。自動処理の失敗警告もここに載る。"""
    business_day = models.ForeignKey(
        BusinessDay, verbose_name='営業日', on_delete=models.CASCADE, related_name='tasks'
    )
    title = models.CharField('タスク名', max_length=200)
    order = models.PositiveSmallIntegerField('表示順', default=0)
    is_done = models.BooleanField('完了', default=False)
    done_at = models.DateTimeField('完了時刻', null=True, blank=True)
    done_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='完了者', on_delete=models.SET_NULL, null=True, blank=True
    )
    # 自動処理が失敗した場合の警告文。空でなければチェックリスト上で目立たせる。
    alert = models.CharField('警告', max_length=255, blank=True)

    class Meta:
        ordering = ['order', 'pk']

    def __str__(self):
        mark = '✓' if self.is_done else '□'
        return f'{mark} {self.title}'

    def mark_done(self, user=None):
        self.is_done = True
        self.done_at = timezone.now()
        self.done_by = user
        self.save(update_fields=['is_done', 'done_at', 'done_by'])
