from django.conf import settings
from django.db import models
from django.utils import timezone

from . import timeslots


class Store(models.Model):
    """店舗"""
    TYPE_FORTUNE = 'fortune'
    TYPE_RESTAURANT = 'restaurant'
    BUSINESS_TYPE_CHOICES = [
        (TYPE_FORTUNE, '占い(スタッフ指名・時間枠)'),
        (TYPE_RESTAURANT, '飲食(座席・人数)'),
    ]

    name = models.CharField('店名', max_length=255)
    business_type = models.CharField('業態', max_length=20, choices=BUSINESS_TYPE_CHOICES, default=TYPE_FORTUNE)
    # 深夜営業対応: 閉店が翌日にまたがる場合は 24+h で表す(例: 18時-翌2時 → 18, 26)。
    # 25時・26時といったナイト業態の慣習表記がそのまま画面に出る。上限は30(翌6時)。
    opening_hour = models.PositiveSmallIntegerField('開店時刻(時)', default=9)
    closing_hour = models.PositiveSmallIntegerField('閉店時刻(時)', default=18)

    # 機能フラグ(店舗ごとにオン/オフ)。オフの機能は画面が404になり、
    # 開店時の自動処理からも除外される。予約カレンダー・チェックリスト・勤怠は
    # 基盤機能のためフラグ化しない。
    enable_sns = models.BooleanField('SNS投稿機能', default=True)
    enable_inventory = models.BooleanField('在庫・発注機能', default=True)
    enable_seat_board = models.BooleanField('座席ボード', default=True)
    enable_gbp = models.BooleanField('Googleマップ(GBP)連携', default=True)

    class Meta:
        constraints = [
            # 開店<閉店、閉店は30時(翌6時)まで、営業は最長24時間。
            # 24時間超を許すと翌日早朝の時刻がどの営業日の枠か曖昧になるため禁止。
            models.CheckConstraint(
                condition=(
                    models.Q(
                        opening_hour__lt=models.F('closing_hour'),
                        opening_hour__lte=23,
                        closing_hour__lte=30,
                    )
                    & models.Q(closing_hour__lte=models.F('opening_hour') + 24)
                ),
                name='store_valid_business_hours',
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def business_hours(self):
        """予約枠の対象となる時刻(時)のリスト。閉店時刻の枠は含まない。

        24以上の値は翌日早朝の枠(25 = 翌1時)。表示・URLにはこの値をそのまま使い、
        実時刻への変換は booking.timeslots が行う。
        """
        return range(self.opening_hour, self.closing_hour)

    def business_slot(self, local_dt):
        """aware datetime(ローカル時刻)を(営業日, 枠時刻)に変換する。"""
        return timeslots.business_slot(self, local_dt)


class Staff(models.Model):
    """店舗スタッフ・キャスト"""
    KIND_STAFF = 'staff'
    KIND_CAST = 'cast'
    KIND_CHOICES = [
        (KIND_STAFF, 'スタッフ'),
        (KIND_CAST, 'キャスト'),
    ]

    name = models.CharField('表示名', max_length=50)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='ログインユーザー', on_delete=models.CASCADE
    )
    store = models.ForeignKey(Store, verbose_name='店舗', on_delete=models.CASCADE)
    kind = models.CharField('区分', max_length=10, choices=KIND_CHOICES, default=KIND_STAFF)
    profile_image = models.ImageField('プロフィール画像', upload_to='staff/', blank=True)
    # SNS投稿に名前・画像を載せてよいか。退職者の誤掲載・顔出しNG事故を防ぐため、
    # SNS文面・画像の生成は必ずこのフラグと is_on_roster を参照する。
    sns_publishable = models.BooleanField('SNS掲載可', default=False)
    is_on_roster = models.BooleanField('在籍中', default=True)
    # 承認権限(SNS投稿の承認・発注の承認/取消/入荷・開閉店・勤怠CSV)。
    # 対外影響・金銭影響のある操作はこのフラグを持つスタッフに限定する。
    is_manager = models.BooleanField('店長(承認権限)', default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'store'], name='unique_staff'),
        ]

    def __str__(self):
        return f'{self.store.name} - {self.name}'


class Seat(models.Model):
    """座席・テーブル"""
    TYPE_COUNTER = 'counter'
    TYPE_TABLE = 'table'
    TYPE_PRIVATE = 'private'
    TYPE_FORTUNE = 'fortune'
    SEAT_TYPE_CHOICES = [
        (TYPE_COUNTER, 'カウンター'),
        (TYPE_TABLE, 'テーブル'),
        (TYPE_PRIVATE, '個室'),
        (TYPE_FORTUNE, '鑑定席'),
    ]

    store = models.ForeignKey(Store, verbose_name='店舗', on_delete=models.CASCADE, related_name='seats')
    name = models.CharField('座席名', max_length=50)
    capacity = models.PositiveSmallIntegerField('定員', default=2)
    seat_type = models.CharField('種別', max_length=10, choices=SEAT_TYPE_CHOICES, default=TYPE_TABLE)
    is_active = models.BooleanField('使用中', default=True)

    class Meta:
        ordering = ['store', 'name']
        constraints = [
            models.UniqueConstraint(fields=['store', 'name'], name='unique_seat_name_per_store'),
        ]

    def __str__(self):
        return f'{self.store.name} - {self.name}'


class Schedule(models.Model):
    """予約スケジュール."""
    start = models.DateTimeField('開始時間')
    end = models.DateTimeField('終了時間')
    name = models.CharField('予約者名', max_length=255)
    staff = models.ForeignKey('Staff', verbose_name='占いスタッフ', on_delete=models.CASCADE)
    seat = models.ForeignKey(
        Seat, verbose_name='座席', on_delete=models.SET_NULL, null=True, blank=True, related_name='schedules'
    )
    party_size = models.PositiveSmallIntegerField('人数', default=1)

    class Meta:
        constraints = [
            # 同一スタッフ・同一開始時刻の予約はDBレベルで禁止(競合状態での二重予約防止)
            models.UniqueConstraint(fields=['staff', 'start'], name='unique_schedule_per_staff_start'),
            # 座席が割当済みなら、同一座席・同一開始時刻の重複割当を禁止
            models.UniqueConstraint(
                fields=['seat', 'start'],
                condition=models.Q(seat__isnull=False),
                name='unique_schedule_per_seat_start',
            ),
        ]

    def __str__(self):
        start = timezone.localtime(self.start).strftime('%Y/%m/%d %H:%M:%S')
        end = timezone.localtime(self.end).strftime('%Y/%m/%d %H:%M:%S')
        return f'{self.name} {start} ~ {end} {self.staff}'


class WalkIn(models.Model):
    """ウォークイン(飛び込み)の着席記録"""
    seat = models.ForeignKey(Seat, verbose_name='座席', on_delete=models.CASCADE, related_name='walkins')
    party_size = models.PositiveSmallIntegerField('人数', default=1)
    seated_at = models.DateTimeField('着席時刻', default=timezone.now)
    left_at = models.DateTimeField('離席時刻', null=True, blank=True)

    class Meta:
        ordering = ['-seated_at']
        constraints = [
            # 同一座席に同時に複数の「着席中」を作れない(同時タップの競合防止)
            models.UniqueConstraint(
                fields=['seat'],
                condition=models.Q(left_at__isnull=True),
                name='unique_active_walkin_per_seat',
            ),
        ]

    def __str__(self):
        return f'{self.seat} {self.party_size}名 {timezone.localtime(self.seated_at):%H:%M}'

    @property
    def is_active(self):
        return self.left_at is None
