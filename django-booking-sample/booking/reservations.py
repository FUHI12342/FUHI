"""顧客向けWeb座席予約(飲食業態)のサービス層。

人数→空き座席候補→確定→確認メール→顧客自身のキャンセル、までを扱う。
ビューはここを呼ぶだけにし、空き判定・トークン発行・メール送信のロジックは
テストしやすいようここに集約する。

座席予約は Schedule(staff=None, seat=座席)として保存し、同一座席・同一開始時刻の
二重予約は DB 制約 unique_schedule_per_seat_start に委ねる(競合時 IntegrityError)。
"""
import datetime
import logging
import secrets

from django.apps import apps
from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Schedule
from .timeslots import make_aware_datetime

logger = logging.getLogger(__name__)

# 何日先まで受け付けるか。遠すぎる予約はノーショー率が上がるため制限する。
MAX_DAYS_AHEAD = 60


class SlotUnavailable(Exception):
    """その座席・時刻はもう予約できない(埋まった・過去・定員不足・営業時間外)。"""


def business_hours_for(store, date):
    """その営業日の枠時刻。営業日(operations.BusinessDay)の臨時営業時間があれば優先する。

    booking は operations に必須依存しないため、モデルは遅延取得する。
    """
    opening, closing = store.opening_hour, store.closing_hour
    if apps.is_installed('operations'):
        BusinessDay = apps.get_model('operations', 'BusinessDay')
        business_day = BusinessDay.objects.filter(store=store, date=date).first()
        if business_day is not None:
            opening, closing = business_day.opening_hour, business_day.closing_hour
    return range(opening, closing)


def slot_label(hour):
    """枠時刻の表示。深夜枠(24以上)は「25:00(翌1:00)」のように併記する。"""
    if hour >= 24:
        return f'{hour}:00(翌{hour - 24}:00)'
    return f'{hour}:00'


def available_slots(store, date, party_size, now=None):
    """指定日・人数で予約できる(枠時刻, 座席候補)の一覧。

    - 座席は使用中(is_active)かつ定員が人数以上のもの
    - その座席・開始時刻に予約が無いもの
    - 開始時刻が現在より後のもの(当日予約は可、過ぎた枠は不可)
    返り値は [{'hour', 'label', 'start', 'seats': [Seat, ...]}, ...]。座席候補が無い枠も
    含める(「満席」と表示するため)。
    """
    now = now or timezone.now()
    seats = list(store.seats.filter(is_active=True, capacity__gte=party_size).order_by('capacity', 'name'))
    hours = business_hours_for(store, date)
    if not seats or not hours:
        return []

    starts = {hour: make_aware_datetime(date.year, date.month, date.day, hour) for hour in hours}
    booked = set(
        Schedule.objects.filter(
            seat__in=seats, start__in=list(starts.values()),
        ).values_list('seat_id', 'start')
    )
    slots = []
    for hour in hours:
        start = starts[hour]
        if start <= now:
            continue
        slots.append({
            'hour': hour,
            'label': slot_label(hour),
            'start': start,
            'seats': [seat for seat in seats if (seat.pk, start) not in booked],
        })
    return slots


def create_reservation(*, store, seat, date, hour, party_size, name, email, phone='', now=None):
    """座席予約を確定する。競合・不整合は SlotUnavailable。

    人数と営業時間は再検証する(候補表示からの時間経過や URL 改変への備え)。
    二重予約の最終判定は DB 制約に委ね、IntegrityError を SlotUnavailable に変換する。
    """
    now = now or timezone.now()
    if seat.store_id != store.pk or not seat.is_active:
        raise SlotUnavailable('この座席は予約できません。')
    if party_size < 1 or party_size > seat.capacity:
        raise SlotUnavailable(f'{seat.name} は定員{seat.capacity}名です。人数を見直してください。')
    if hour not in business_hours_for(store, date):
        raise SlotUnavailable('営業時間外です。')
    start = make_aware_datetime(date.year, date.month, date.day, hour)
    if start <= now:
        raise SlotUnavailable('過ぎた時間は予約できません。')
    if date > timezone.localdate() + datetime.timedelta(days=MAX_DAYS_AHEAD):
        raise SlotUnavailable(f'予約は{MAX_DAYS_AHEAD}日先まで受け付けています。')

    try:
        with transaction.atomic():
            return Schedule.objects.create(
                staff=None, seat=seat, start=start, end=start + datetime.timedelta(hours=1),
                name=name, party_size=party_size,
                customer_email=email, customer_phone=phone,
                cancel_token=secrets.token_urlsafe(32),
            )
    except IntegrityError:
        raise SlotUnavailable('すみません、入れ違いでこの席が埋まりました。別の席・時間はどうですか。')


def cancel_reservation(schedule):
    """顧客自身によるキャンセル。開始時刻を過ぎていれば False(店舗連絡に誘導)。"""
    if not schedule.is_cancellable:
        return False
    schedule.delete()
    return True


def send_confirmation_email(schedule, detail_url):
    """予約確認メール(取消リンク付き)。送信失敗は予約自体を妨げず False を返す。

    SMTP 未設定(開発既定のコンソールバックエンド)でも例外にはならない。
    """
    if not schedule.customer_email:
        return False
    store = schedule.seat.store
    local_start = timezone.localtime(schedule.start)
    body = (
        f'{schedule.name} 様\n\n'
        f'{store.name} のご予約を承りました。\n\n'
        f'日時: {local_start:%Y/%m/%d %H:%M}〜\n'
        f'人数: {schedule.party_size}名\n'
        f'席: {schedule.seat.name}({schedule.seat.get_seat_type_display()})\n\n'
        f'ご予約の確認・キャンセルは以下のURLから行えます(開始時刻まで)。\n'
        f'{detail_url}\n\n'
        f'ご都合が悪くなった場合は、無断キャンセルではなく上記URLからのキャンセルをお願いします。\n'
    )
    try:
        send_mail(
            subject=f'【{store.name}】ご予約確認({local_start:%m/%d %H:%M})',
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[schedule.customer_email],
        )
    except Exception:  # noqa: BLE001 - メール障害で予約を失敗扱いにしない
        logger.warning('予約確認メールの送信に失敗: schedule=%s', schedule.pk, exc_info=True)
        return False
    return True
