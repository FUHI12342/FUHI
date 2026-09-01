"""顧客向けWeb座席予約(飲食業態・ログイン不要)のテスト。"""
import datetime

from django.contrib.auth import get_user_model
from django.core import mail
from django.db import IntegrityError, transaction
from django.shortcuts import resolve_url
from django.test import TestCase
from django.utils import timezone

from booking import reservations
from booking.models import Schedule, Seat, Store
from booking.timeslots import make_aware_datetime
from operations.models import BusinessDay


def tomorrow():
    return timezone.localdate() + datetime.timedelta(days=1)


class WebReservationTestCase(TestCase):
    """18時〜翌2時(26時)営業の飲食店に、1名席・4名席・6名個室がある前提。"""

    def setUp(self):
        self.store = Store.objects.create(
            name='深夜食堂', business_type=Store.TYPE_RESTAURANT, opening_hour=18, closing_hour=26,
        )
        self.counter = Seat.objects.create(store=self.store, name='C1', seat_type=Seat.TYPE_COUNTER, capacity=1)
        self.table = Seat.objects.create(store=self.store, name='T1', seat_type=Seat.TYPE_TABLE, capacity=4)
        self.room = Seat.objects.create(store=self.store, name='V1', seat_type=Seat.TYPE_PRIVATE, capacity=6)
        self.date = tomorrow()

    def search_url(self, party_size=2, date=None):
        date = date or self.date
        return f"{resolve_url('booking:web_reservation', pk=self.store.pk)}?date={date.isoformat()}&party_size={party_size}"

    def confirm_url(self, seat, hour=20, party_size=2, date=None):
        date = date or self.date
        url = resolve_url(
            'booking:web_reservation_confirm', pk=self.store.pk,
            year=date.year, month=date.month, day=date.day, hour=hour, seat_pk=seat.pk,
        )
        return f'{url}?party_size={party_size}'

    def reserve(self, seat, hour=20, party_size=2, date=None, **extra):
        data = {'name': '山田', 'customer_email': 'yamada@example.com', 'customer_phone': '', 'party_size': party_size}
        data.update(extra)
        return self.client.post(self.confirm_url(seat, hour=hour, party_size=party_size, date=date), data, follow=True)


class WebReservationAccessTests(WebReservationTestCase):

    def test_store_list_links_restaurant_to_reservation(self):
        response = self.client.get(resolve_url('booking:store_list'))
        self.assertContains(response, resolve_url('booking:web_reservation', pk=self.store.pk))

    def test_fortune_store_is_not_reservable(self):
        fortune = Store.objects.create(name='占い館', business_type=Store.TYPE_FORTUNE)
        response = self.client.get(resolve_url('booking:web_reservation', pk=fortune.pk))
        self.assertEqual(response.status_code, 404)
        response = self.client.get(resolve_url('booking:store_list'))
        self.assertNotContains(response, resolve_url('booking:web_reservation', pk=fortune.pk))

    def test_feature_flag_off_returns_404(self):
        self.store.enable_web_reservation = False
        self.store.save()
        self.assertEqual(self.client.get(resolve_url('booking:web_reservation', pk=self.store.pk)).status_code, 404)
        self.assertEqual(self.client.get(self.confirm_url(self.table)).status_code, 404)
        self.assertEqual(self.reserve(self.table).status_code, 404)
        self.assertFalse(Schedule.objects.exists())

    def test_no_login_required(self):
        response = self.client.get(self.search_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '深夜食堂 席を予約する')


class AvailableSlotsTests(WebReservationTestCase):

    def test_seats_filtered_by_capacity(self):
        slots = reservations.available_slots(self.store, self.date, party_size=3)
        self.assertEqual([slot['hour'] for slot in slots], list(range(18, 26)))
        self.assertEqual([seat.name for seat in slots[0]['seats']], ['T1', 'V1'])

    def test_booked_seat_is_excluded_for_that_hour_only(self):
        start = make_aware_datetime(self.date.year, self.date.month, self.date.day, 20)
        Schedule.objects.create(seat=self.table, start=start, end=start + datetime.timedelta(hours=1), name='先客')
        by_hour = {slot['hour']: [s.name for s in slot['seats']] for slot in
                   reservations.available_slots(self.store, self.date, party_size=2)}
        self.assertEqual(by_hour[20], ['V1'])
        self.assertEqual(by_hour[21], ['T1', 'V1'])

    def test_past_slots_are_hidden_but_later_today_is_open(self):
        today = timezone.localdate()
        now = make_aware_datetime(today.year, today.month, today.day, 20) + datetime.timedelta(minutes=30)
        slots = reservations.available_slots(self.store, today, party_size=1, now=now)
        # 20:30 時点: 18〜20時の枠は過ぎている。21時以降と深夜枠(25時=翌1時)は予約可
        self.assertEqual([slot['hour'] for slot in slots], [21, 22, 23, 24, 25])
        self.assertEqual(slots[-1]['label'], '25:00(翌1:00)')

    def test_late_night_slot_maps_to_next_calendar_day(self):
        slots = reservations.available_slots(self.store, self.date, party_size=1)
        slot_25 = next(slot for slot in slots if slot['hour'] == 25)
        local = timezone.localtime(slot_25['start'])
        self.assertEqual((local.date(), local.hour), (self.date + datetime.timedelta(days=1), 1))

    def test_business_day_override_hours_are_respected(self):
        # 臨時に 20時〜24時 営業にした日は、その範囲だけ候補になる
        BusinessDay.objects.create(store=self.store, date=self.date, opening_hour_override=20, closing_hour_override=24)
        slots = reservations.available_slots(self.store, self.date, party_size=1)
        self.assertEqual([slot['hour'] for slot in slots], [20, 21, 22, 23])

    def test_search_page_shows_candidates_and_full_marks(self):
        start = make_aware_datetime(self.date.year, self.date.month, self.date.day, 20)
        for seat in (self.table, self.room):
            Schedule.objects.create(seat=seat, start=start, end=start + datetime.timedelta(hours=1), name='先客')
        response = self.client.get(self.search_url(party_size=3))
        self.assertContains(response, '満席')
        self.assertContains(response, self.confirm_url(self.table, hour=21, party_size=3))
        self.assertNotContains(response, self.confirm_url(self.table, hour=20, party_size=3))

    def test_search_rejects_past_date(self):
        yesterday = timezone.localdate() - datetime.timedelta(days=1)
        response = self.client.get(self.search_url(date=yesterday))
        self.assertContains(response, '過ぎた日付は選べません。')
        self.assertIsNone(response.context['slots'])


class ReserveAndCancelTests(WebReservationTestCase):

    def test_reserve_creates_seat_schedule_and_sends_mail(self):
        response = self.reserve(self.table, hour=25, party_size=3, customer_phone='090-0000-0000')
        schedule = Schedule.objects.get()
        self.assertIsNone(schedule.staff)
        self.assertEqual(schedule.seat, self.table)
        self.assertEqual(schedule.party_size, 3)
        self.assertEqual(schedule.customer_email, 'yamada@example.com')
        self.assertEqual(schedule.customer_phone, '090-0000-0000')
        self.assertTrue(schedule.cancel_token)
        # 25時枠 = 翌日 1:00
        local = timezone.localtime(schedule.start)
        self.assertEqual((local.date(), local.hour), (self.date + datetime.timedelta(days=1), 1))

        # 確認画面へ遷移し、確認メールに取消URLが入る
        detail_url = resolve_url('booking:web_reservation_detail', token=schedule.cancel_token)
        self.assertEqual(response.request['PATH_INFO'], detail_url)
        self.assertContains(response, '山田 様')
        self.assertContains(response, '予約をキャンセルする')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['yamada@example.com'])
        self.assertIn(detail_url, mail.outbox[0].body)
        self.assertIn('深夜食堂', mail.outbox[0].subject)

    def test_reservation_appears_on_seat_board(self):
        today = timezone.localdate()
        now = make_aware_datetime(today.year, today.month, today.day, 18)
        # 当日 23 時の枠を予約(テスト実行時刻に依らないよう now を固定して直接作成)
        schedule = reservations.create_reservation(
            store=self.store, seat=self.table, date=today, hour=23, party_size=2,
            name='佐藤', email='sato@example.com', now=now,
        )
        self.assertTrue(schedule.is_web_reservation)
        self.client.force_login(get_user_model().objects.create_superuser('root', 'root@example.com', 'rootpass123'))
        response = self.client.get(resolve_url('booking:seat_board', pk=self.store.pk))
        self.assertContains(response, '佐藤(2名)')

    def test_email_is_required(self):
        response = self.reserve(self.table, customer_email='')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'このフィールドは必須です')
        self.assertFalse(Schedule.objects.exists())

    def test_party_size_over_capacity_is_rejected(self):
        response = self.reserve(self.counter, party_size=2)
        messages = [str(m) for m in response.context['messages']]
        self.assertEqual(messages, ['C1 は定員1名です。人数を見直してください。'])
        self.assertFalse(Schedule.objects.exists())

    def test_double_booking_is_rejected_with_message(self):
        self.reserve(self.table, hour=20)
        response = self.reserve(self.table, hour=20, customer_email='other@example.com')
        messages = [str(m) for m in response.context['messages']]
        self.assertIn('すみません、入れ違いでこの席が埋まりました。別の席・時間はどうですか。', messages)
        self.assertEqual(Schedule.objects.count(), 1)
        # 候補画面に戻り、同人数・同日の検索が引き継がれる
        self.assertEqual(response.request['QUERY_STRING'], f'date={self.date.isoformat()}&party_size=2')

    def test_outside_business_hours_is_rejected(self):
        response = self.reserve(self.table, hour=17)
        messages = [str(m) for m in response.context['messages']]
        self.assertEqual(messages, ['営業時間外です。'])
        self.assertFalse(Schedule.objects.exists())

    def test_seat_of_other_store_is_404(self):
        other = Store.objects.create(name='別店', business_type=Store.TYPE_RESTAURANT, opening_hour=18, closing_hour=26)
        seat = Seat.objects.create(store=other, name='X1', capacity=4)
        self.assertEqual(self.reserve(seat).status_code, 404)

    def test_cancel_before_start_deletes_reservation(self):
        self.reserve(self.table, hour=20)
        schedule = Schedule.objects.get()
        response = self.client.post(
            resolve_url('booking:web_reservation_cancel', token=schedule.cancel_token), follow=True,
        )
        self.assertFalse(Schedule.objects.exists())
        self.assertContains(response, 'ご予約をキャンセルしました。')
        # 取消済みトークンは 404
        self.assertEqual(
            self.client.get(resolve_url('booking:web_reservation_detail', token=schedule.cancel_token)).status_code, 404
        )

    def test_cancel_after_start_is_refused(self):
        start = timezone.now() - datetime.timedelta(minutes=10)
        schedule = Schedule.objects.create(
            seat=self.table, start=start, end=start + datetime.timedelta(hours=1),
            name='遅刻', customer_email='late@example.com', cancel_token='token-late',
        )
        response = self.client.post(resolve_url('booking:web_reservation_cancel', token='token-late'), follow=True)
        self.assertTrue(Schedule.objects.filter(pk=schedule.pk).exists())
        self.assertContains(response, '開始時刻を過ぎた予約はこの画面から取り消せません。')
        self.assertNotContains(response, '予約をキャンセルする')

    def test_unknown_token_is_404(self):
        self.assertEqual(self.client.get(resolve_url('booking:web_reservation_detail', token='nope')).status_code, 404)

    def test_confirmation_mail_failure_does_not_lose_reservation(self):
        with self.settings(EMAIL_BACKEND='booking.tests.test_web_reservation.BrokenEmailBackend'), \
                self.assertLogs('booking.reservations', level='WARNING'):
            response = self.reserve(self.table, hour=21)
        self.assertEqual(Schedule.objects.count(), 1)
        messages = [str(m) for m in response.context['messages']]
        self.assertIn('確認メールを送れませんでした。この画面のURLを控えてください。', messages)


class ScheduleConstraintTests(WebReservationTestCase):

    def test_schedule_without_staff_and_seat_is_rejected(self):
        start = timezone.now()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Schedule.objects.create(start=start, end=start + datetime.timedelta(hours=1), name='宙に浮いた予約')

    def test_seat_reservations_without_staff_do_not_collide_on_staff_constraint(self):
        # staff が NULL 同士は「同一スタッフ」ではないので、同時刻に別座席の予約が並べる
        start = timezone.now() + datetime.timedelta(days=1)
        Schedule.objects.create(seat=self.table, start=start, end=start + datetime.timedelta(hours=1), name='A')
        Schedule.objects.create(seat=self.room, start=start, end=start + datetime.timedelta(hours=1), name='B')
        self.assertEqual(Schedule.objects.filter(start=start).count(), 2)


class BrokenEmailBackend:
    """送信が必ず失敗するメールバックエンド(障害時の挙動確認用)。"""

    def __init__(self, *args, **kwargs):
        pass

    def send_messages(self, messages):
        raise ConnectionError('SMTP down')
