"""営業時間スロットと実時刻の相互変換。

このシステムの「時刻」は営業日基準で、24 以上の値は翌日早朝を表す(25 = 翌1時)。
深夜営業の店舗では翌日早朝の実時刻を前営業日の枠として扱う。変換ロジックは
ここに集約し、ビュー・モデル・他アプリはこのモジュールを経由する。
"""
import datetime

from django.utils import timezone


def make_aware_datetime(year, month, day, hour):
    """営業日の年月日と枠時刻(24以上可)から、現在タイムゾーンの aware datetime を作る。"""
    naive = datetime.datetime(year=year, month=month, day=day) + datetime.timedelta(hours=hour)
    return timezone.make_aware(naive, timezone.get_current_timezone())


def business_slot(store, local_dt):
    """ローカルの aware datetime を (営業日, 枠時刻) に変換する。

    閉店が 24 時を超える店舗では、閉店-24 時より前の早朝時刻を前日の 24+h 枠にする。
    """
    hour = local_dt.hour
    date = local_dt.date()
    if store.closing_hour > 24 and hour < store.closing_hour - 24:
        return date - datetime.timedelta(days=1), hour + 24
    return date, hour


def business_day_span(store, date):
    """営業日の開店枠の開始時刻と、最終枠の終了時刻(排他的)を返す。"""
    hours = store.business_hours
    start = make_aware_datetime(date.year, date.month, date.day, hours[0])
    end = make_aware_datetime(date.year, date.month, date.day, hours[-1]) + datetime.timedelta(hours=1)
    return start, end


def calendar_day_range(date):
    """暦日(0:00〜翌0:00)の aware な範囲。入出庫など暦日単位の集計に使う。"""
    tz = timezone.get_current_timezone()
    start = datetime.datetime.combine(date, datetime.time.min, tzinfo=tz)
    return start, start + datetime.timedelta(days=1)
