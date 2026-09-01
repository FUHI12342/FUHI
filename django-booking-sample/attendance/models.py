from django.conf import settings
from django.db import models
from django.utils import timezone

from booking.models import Staff


class ShiftQuerySet(models.QuerySet):
    def on_duty(self, store, date):
        """指定日にその店舗で出勤予定(欠勤以外)のシフト。"""
        return (
            self.filter(staff__store=store, date=date)
            .exclude(status=Shift.STATUS_ABSENT)
            .select_related('staff')
            .order_by('start_time')
        )

    def publishable_casts(self, store, date):
        """SNSに掲載してよい出勤キャストのシフト。

        在籍中かつSNS掲載可のスタッフに限定する(退職者・顔出しNGの誤掲載防止)。
        """
        return self.on_duty(store, date).filter(
            staff__sns_publishable=True,
            staff__is_on_roster=True,
        )


class Shift(models.Model):
    """シフト(出勤予定)"""
    STATUS_PLANNED = 'planned'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_ABSENT = 'absent'
    STATUS_CHOICES = [
        (STATUS_PLANNED, '予定'),
        (STATUS_CONFIRMED, '確定'),
        (STATUS_ABSENT, '欠勤'),
    ]

    staff = models.ForeignKey(Staff, verbose_name='スタッフ', on_delete=models.CASCADE, related_name='shifts')
    date = models.DateField('日付')
    start_time = models.TimeField('開始')
    end_time = models.TimeField('終了')
    status = models.CharField('状態', max_length=10, choices=STATUS_CHOICES, default=STATUS_PLANNED)
    note = models.CharField('メモ', max_length=255, blank=True)

    objects = ShiftQuerySet.as_manager()

    class Meta:
        ordering = ['date', 'start_time']
        constraints = [
            models.UniqueConstraint(fields=['staff', 'date', 'start_time'], name='unique_shift'),
        ]

    def __str__(self):
        return f'{self.date} {self.staff.name} {self.start_time:%H:%M}-{self.end_time:%H:%M} ({self.get_status_display()})'


class TimeRecord(models.Model):
    """出退勤の打刻記録"""
    staff = models.ForeignKey(Staff, verbose_name='スタッフ', on_delete=models.CASCADE, related_name='time_records')
    date = models.DateField('日付')
    clock_in = models.DateTimeField('出勤打刻', null=True, blank=True)
    clock_out = models.DateTimeField('退勤打刻', null=True, blank=True)

    class Meta:
        ordering = ['-date']
        constraints = [
            models.UniqueConstraint(fields=['staff', 'date'], name='unique_time_record_per_day'),
        ]

    def __str__(self):
        return f'{self.date} {self.staff.name}'

    @property
    def worked_minutes(self):
        if self.clock_in and self.clock_out:
            return int((self.clock_out - self.clock_in).total_seconds() // 60)
        return None


def confirm_shifts(store, date):
    """指定日の「予定」シフトを一括で「確定」にする(開店処理から呼ばれる)。"""
    return Shift.objects.filter(staff__store=store, date=date, status=Shift.STATUS_PLANNED).update(
        status=Shift.STATUS_CONFIRMED
    )
