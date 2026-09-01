from django.conf import settings
from django.db import models
from django.utils import timezone


class Store(models.Model):
    """店舗"""
    name = models.CharField('店名', max_length=255)
    opening_hour = models.PositiveSmallIntegerField('開店時刻(時)', default=9)
    closing_hour = models.PositiveSmallIntegerField('閉店時刻(時)', default=18)

    def __str__(self):
        return self.name

    @property
    def business_hours(self):
        """予約枠の対象となる時刻(時)のリスト。閉店時刻の枠は含まない。"""
        return range(self.opening_hour, self.closing_hour)


class Staff(models.Model):
    """店舗スタッフ"""
    name = models.CharField('表示名', max_length=50)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='ログインユーザー', on_delete=models.CASCADE
    )
    store = models.ForeignKey(Store, verbose_name='店舗', on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'store'], name='unique_staff'),
        ]

    def __str__(self):
        return f'{self.store.name} - {self.name}'


class Schedule(models.Model):
    """予約スケジュール."""
    start = models.DateTimeField('開始時間')
    end = models.DateTimeField('終了時間')
    name = models.CharField('予約者名', max_length=255)
    staff = models.ForeignKey('Staff', verbose_name='占いスタッフ', on_delete=models.CASCADE)

    class Meta:
        constraints = [
            # 同一スタッフ・同一開始時刻の予約はDBレベルで禁止(競合状態での二重予約防止)
            models.UniqueConstraint(fields=['staff', 'start'], name='unique_schedule_per_staff_start'),
        ]

    def __str__(self):
        start = timezone.localtime(self.start).strftime('%Y/%m/%d %H:%M:%S')
        end = timezone.localtime(self.end).strftime('%Y/%m/%d %H:%M:%S')
        return f'{self.name} {start} ~ {end} {self.staff}'
