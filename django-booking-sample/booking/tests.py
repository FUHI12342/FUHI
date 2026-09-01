import datetime
from django.shortcuts import resolve_url, get_object_or_404
from django.test import TestCase
from django.template.exceptions import TemplateDoesNotExist
from django.utils import timezone
from .models import Schedule, Staff

batu = '×'
maru = '○'
line = '-'


class StoreListViewTests(TestCase):
    fixtures = ['initial']

    def test_get(self):
        """店舗の一覧が表示されるかテスト"""
        response = self.client.get(resolve_url('booking:store_list'))
        self.assertQuerySetEqual(response.context['store_list'], ['店舗A', '店舗B', '店舗C'], transform=str)


class StaffListViewTests(TestCase):
    fixtures = ['initial']

    def test_store_a(self):
        """店舗Aのスタッフリストの確認"""
        response = self.client.get(resolve_url('booking:staff_list', pk=1))
        self.assertQuerySetEqual(response.context['staff_list'], ['店舗A - じゃば', '店舗A - ぱいそん'], transform=str)

    def test_store_b(self):
        """店舗Bのスタッフリストの確認"""
        response = self.client.get(resolve_url('booking:staff_list', pk=2))
        self.assertQuerySetEqual(response.context['staff_list'], ['店舗B - じゃんご'], transform=str)

    def test_store_c(self):
        """店舗Cのスタッフリストの確認。店舗Cには誰もいない"""
        response = self.client.get(resolve_url('booking:staff_list', pk=3))
        self.assertQuerySetEqual(response.context['staff_list'], [])


class StaffCalendarViewTests(TestCase):
    fixtures = ['initial']

    def test_no_schedule(self):
        """スケジュールがない場合のカレンダーをテスト。

        店名や表示期間と、「☓」がないことを確認。これがあるのはスケジュールがある場合。
        """
        start = timezone.localtime()
        end = start + datetime.timedelta(days=6)
        response = self.client.get(resolve_url('booking:calendar', pk=1))
        self.assertContains(response, '店舗A店 ぱいそん')
        self.assertContains(response, f'{start.year}年{start.month}月{start.day}日 - {end.year}年{end.month}月{end.day}日')
        self.assertContains(response, line)
        self.assertContains(response, maru)
        self.assertNotContains(response, batu)

    def test_one_schedule_next_day_9(self):
        """スケジュールが次の日の9時

        スケジュールがあるので、☓がカレンダー内に表示されることを確認
        """
        staff = get_object_or_404(Staff, pk=1)
        start = timezone.localtime() + datetime.timedelta(days=1)
        start = start.replace(hour=9, minute=0, second=0)
        end = start + datetime.timedelta(hours=1)
        Schedule.objects.create(staff=staff, start=start, end=end, name='テスト')
        response = self.client.get(resolve_url('booking:calendar', pk=staff.pk))
        self.assertContains(response, line)
        self.assertContains(response, maru)
        self.assertContains(response, batu)

    def test_one_schedule_next_day_8(self):
        """スケジュールが次の日の8時

        8時のスケジュールはカレンダーに表示されないので、☓がないことを確認
        """
        staff = get_object_or_404(Staff, pk=1)
        start = timezone.localtime() + datetime.timedelta(days=1)
        start = start.replace(hour=8, minute=0, second=0)
        end = start + datetime.timedelta(hours=1)
        Schedule.objects.create(staff=staff, start=start, end=end, name='テスト')
        response = self.client.get(resolve_url('booking:calendar', pk=staff.pk))
        self.assertContains(response, line)
        self.assertContains(response, maru)
        self.assertNotContains(response, batu)

    def test_one_schedule_next_day_17(self):
        """スケジュールが次の日の17時

        17時はカレンダーに表示されるので、☓があることを確認
        """
        staff = get_object_or_404(Staff, pk=1)
        start = timezone.localtime() + datetime.timedelta(days=1)
        start = start.replace(hour=17, minute=0, second=0)
        end = start + datetime.timedelta(hours=1)
        Schedule.objects.create(staff=staff, start=start, end=end, name='テスト')
        response = self.client.get(resolve_url('booking:calendar', pk=staff.pk))
        self.assertContains(response, line)
        self.assertContains(response, maru)
        self.assertContains(response, batu)

    def test_one_schedule_next_day_18(self):
        """次の日の18時にスケジュール

        18時はカレンダー表示されないので、☓がないことを確認
        """
        staff = get_object_or_404(Staff, pk=1)
        start = timezone.localtime() + datetime.timedelta(days=1)
        start = start.replace(hour=18, minute=0, second=0)
        end = start + datetime.timedelta(hours=1)
        Schedule.objects.create(staff=staff, start=start, end=end, name='テスト')
        response = self.client.get(resolve_url('booking:calendar', pk=staff.pk))
        self.assertContains(response, line)
        self.assertContains(response, maru)
        self.assertNotContains(response, batu)

    def test_one_schedule_before_day_9(self):
        """前の日の9時にスケジュール

        カレンダーは当日から表示なので、前の日のものは表示されない。☓がないことを確認。
        """
        staff = get_object_or_404(Staff, pk=1)
        start = timezone.localtime() - datetime.timedelta(days=1)
        start = start.replace(hour=9, minute=0, second=0)
        end = start + datetime.timedelta(hours=1)
        Schedule.objects.create(staff=staff, start=start, end=end, name='テスト')
        response = self.client.get(resolve_url('booking:calendar', pk=staff.pk))
        self.assertContains(response, line)
        self.assertContains(response, maru)
        self.assertNotContains(response, batu)

    def test_one_schedule_next_week_9(self):
        """来週の9時にスケジュール

        7日後は表示されない。☓がないことを確認
        """
        staff = get_object_or_404(Staff, pk=1)
        start = timezone.localtime() + datetime.timedelta(days=7)
        start = start.replace(hour=9, minute=0, second=0)
        end = start + datetime.timedelta(hours=1)
        Schedule.objects.create(staff=staff, start=start, end=end, name='テスト')
        response = self.client.get(resolve_url('booking:calendar', pk=staff.pk))
        self.assertContains(response, line)
        self.assertContains(response, maru)
        self.assertNotContains(response, batu)

    def test_one_schedule_next_week_9_and_move(self):
        """来週の9時にスケジュール

        7日後を基準にカレンダー表示するので、スケジュールは表示される。☓があることを確認。
        """
        staff = get_object_or_404(Staff, pk=1)
        start = timezone.localtime() + datetime.timedelta(days=7)
        start = start.replace(hour=9, minute=0, second=0)
        end = start + datetime.timedelta(hours=1)
        Schedule.objects.create(staff=staff, start=start, end=end, name='テスト')
        response = self.client.get(resolve_url('booking:calendar', pk=staff.pk, year=start.year, month=start.month, day=start.day))
        self.assertContains(response, line)
        self.assertContains(response, maru)
        self.assertContains(response, batu)

        end = start + datetime.timedelta(days=6)
        self.assertContains(response, '店舗A店 ぱいそん')
        self.assertContains(response, f'{start.year}年{start.month}月{start.day}日 - {end.year}年{end.month}月{end.day}日')


class BookingViewTests(TestCase):
    fixtures = ['initial']

    def test_get(self):
        """予約ページが表示されるかテスト"""
        now = timezone.localtime()
        response = self.client.get(resolve_url('booking:booking', pk=1, year=now.year, month=now.month, day=now.day, hour=9))
        self.assertContains(response, '店舗A店 ぱいそん')
        self.assertContains(response, f'{now.year}年{now.month}月{now.day}日 9時に予約')

    def test_post(self):
        """予約後に、カレンダーページで☓（予約あり）があることを確認"""
        now = timezone.localtime() + datetime.timedelta(days=1)
        response = self.client.post(
            resolve_url('booking:booking', pk=1, year=now.year, month=now.month, day=now.day, hour=9),
            {'name': 'テスト'},
            follow=True
        )
        messages = list(response.context['messages'])
        self.assertEqual(messages, [])
        self.assertContains(response, batu)

    def test_post_exists_data(self):
        """既に埋まった時間に予約した場合に、メッセージ表示があることを確認"""
        now = timezone.localtime().replace(hour=9, minute=0, second=0, microsecond=0)
        end = now + datetime.timedelta(hours=1)
        staff = get_object_or_404(Staff, pk=1)
        Schedule.objects.create(staff=staff, start=now, end=end, name='埋めた')
        response = self.client.post(
            resolve_url('booking:booking', pk=1, year=now.year, month=now.month, day=now.day, hour=9),
            {'name': 'これは入らない'},
            follow=True
        )
        messages = list(response.context['messages'])
        self.assertEqual(str(messages[0]), 'すみません、入れ違いで予約がありました。別の日時はどうですか。')


class MyPageViewTests(TestCase):
    fixtures = ['initial']

    def test_anonymous(self):
        """ログインしていない場合、ログインページにリダイレクトされることを確認"""
        response = self.client.get(resolve_url('booking:my_page'))
        self.assertRedirects(response, '/login/?next=%2Fmypage%2F')

    def test_login_admin(self):
        """管理者でログインした場合。店舗スタッフではないので、ナニも表示されない"""
        self.client.login(username='admin', password='admin123')
        response = self.client.get(resolve_url('booking:my_page'))
        self.assertQuerySetEqual(response.context['staff_list'], [])
        self.assertQuerySetEqual(response.context['schedule_list'], [])
        self.assertContains(response, 'adminのマイページ')

    def test_login_tanaka(self):
        """田中でログイン。スタッフデータが表示されることを確認"""
        self.client.login(username='tanakataro', password='helloworld123')
        response = self.client.get(resolve_url('booking:my_page'))
        self.assertQuerySetEqual(response.context['staff_list'], ['店舗B - じゃんご', '店舗A - ぱいそん'], transform=str)
        self.assertQuerySetEqual(response.context['schedule_list'], [])
        self.assertContains(response, 'tanakataroのマイページ')

    def test_login_tanaka_with_schedule(self):
        """田中でログインし、予約がある場合、自分担当の予約だけ表示されるか確認。"""
        staff1 = get_object_or_404(Staff, pk=1)
        staff2 = get_object_or_404(Staff, pk=2)
        staff3 = get_object_or_404(Staff, pk=3)
        now = timezone.localtime()
        s1 = Schedule.objects.create(staff=staff1, start=now - datetime.timedelta(hours=1), end=now, name='テスト1')  # 過去の予約は表示されない
        s2 = Schedule.objects.create(staff=staff1, start=now + datetime.timedelta(hours=1), end=now, name='テスト2')  # 問題なく表示
        s3 = Schedule.objects.create(staff=staff2, start=now + datetime.timedelta(hours=1), end=now, name='テスト3')  # 問題なく表示
        s4 = Schedule.objects.create(staff=staff3, start=now + datetime.timedelta(hours=1), end=now, name='テスト4')  # staff3は、自分じゃない
        self.client.login(username='tanakataro', password='helloworld123')
        response = self.client.get(resolve_url('booking:my_page'))
        self.assertEqual(list(response.context['schedule_list']), [s2, s3])

    def test_login_yosida_with_schedule(self):
        """吉田でログインし、予約ある場合、自分担当の予約が表示されるか確認"""
        staff1 = get_object_or_404(Staff, pk=1)
        staff2 = get_object_or_404(Staff, pk=2)
        staff3 = get_object_or_404(Staff, pk=3)
        now = timezone.localtime()
        s1 = Schedule.objects.create(staff=staff1, start=now - datetime.timedelta(hours=1), end=now, name='テスト1')
        s2 = Schedule.objects.create(staff=staff1, start=now + datetime.timedelta(hours=1), end=now, name='テスト2')
        s3 = Schedule.objects.create(staff=staff2, start=now + datetime.timedelta(hours=1), end=now, name='テスト3')
        s4 = Schedule.objects.create(staff=staff3, start=now + datetime.timedelta(hours=1), end=now, name='テスト4')  # 吉田の予約
        self.client.login(username='yosidaziro', password='helloworld123')
        response = self.client.get(resolve_url('booking:my_page'))
        self.assertEqual(list(response.context['schedule_list']), [s4])
        self.assertContains(response, 'yosidaziroのマイページ')


class MyPageWithPkViewTests(TestCase):
    fixtures = ['initial']

    def test_anonymous(self):
        """ログインしていない場合、403の表示"""
        response = self.client.get(resolve_url('booking:my_page_with_pk', pk=2))
        self.assertEqual(response.status_code, 403)

    def test_login_admin(self):
        """スーパーユーザーは、どのユーザーのマイページでも見れる"""
        self.client.login(username='admin', password='admin123')
        response = self.client.get(resolve_url('booking:my_page_with_pk', pk=2))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'tanakataroのマイページ')

    def test_login_tanaka(self):
        """自分自身のマイページは見れる"""
        self.client.login(username='tanakataro', password='helloworld123')
        response = self.client.get(resolve_url('booking:my_page_with_pk', pk=2))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'tanakataroのマイページ')

    def test_login_yosida(self):
        """他人のマイページは見れない"""
        self.client.login(username='yosidaziro', password='helloworld123')
        response = self.client.get(resolve_url('booking:my_page_with_pk', pk=2))
        self.assertEqual(response.status_code, 403)

    def test_not_exist_user(self):
        """存在しないユーザーページにスーパーユーザーで行くと、404"""
        self.client.login(username='admin', password='admin123')
        response = self.client.get(resolve_url('booking:my_page_with_pk', pk=10000))
        self.assertEqual(response.status_code, 404)

    def test_not_exist_user(self):
        """存在しないユーザーページに一般ユーザーで行くと、403"""
        self.client.login(username='tanakataro', password='helloworld123')
        response = self.client.get(resolve_url('booking:my_page_with_pk', pk=10000))
        self.assertEqual(response.status_code, 403)


class MyPageCalendarViewTests(TestCase):
    fixtures = ['initial']

    def test_anonymous(self):
        """ログインしていない場合は403"""
        response = self.client.get(resolve_url('booking:my_page_calendar', pk=1))
        self.assertEqual(response.status_code, 403)

    def test_login_admin(self):
        """スーパーユーザーは、誰のカレンダーでも見れる"""
        self.client.login(username='admin', password='admin123')
        response = self.client.get(resolve_url('booking:my_page_calendar', pk=1))
        self.assertEqual(response.status_code, 200)

    def test_login_tanaka(self):
        """自分用のカレンダーは見れる"""
        self.client.login(username='tanakataro', password='helloworld123')
        response = self.client.get(resolve_url('booking:my_page_calendar', pk=1))
        self.assertEqual(response.status_code, 200)
        start = timezone.localtime()
        end = start + datetime.timedelta(days=6)
        self.assertContains(response, '店舗A店 ぱいそん')
        self.assertContains(response, f'{start.year}年{start.month}月{start.day}日 - {end.year}年{end.month}月{end.day}日')
        self.assertContains(response, line)
        self.assertContains(response, maru)
        self.assertNotContains(response, batu)

    def test_login_yosida(self):
        """他人のカレンダーは見れない"""
        self.client.login(username='yosidaziro', password='helloworld123')
        response = self.client.get(resolve_url('booking:my_page_calendar', pk=1))
        self.assertEqual(response.status_code, 403)


class MyPageDayDetailViewTests(TestCase):
    fixtures = ['initial']

    def test_no_schedule(self):
        """店舗や日にちが正しく表示されるかの確認"""
        self.client.login(username='tanakataro', password='helloworld123')
        staff = get_object_or_404(Staff, pk=1)
        now = timezone.localtime().replace(hour=9, minute=0, second=0)
        response = self.client.get(resolve_url('booking:my_page_day_detail', pk=staff.pk, year=now.year, month=now.month, day=now.day))
        self.assertContains(response, '店舗A店 ぱいそん')
        self.assertContains(response, f'{now.year}年{now.month}月{now.day}日の予約一覧')

    def test_one_schedule_9(self):
        """予約が正しく表示されることを確認"""
        self.client.login(username='tanakataro', password='helloworld123')
        staff = get_object_or_404(Staff, pk=1)
        now = timezone.localtime().replace(hour=9, minute=0, second=0)
        Schedule.objects.create(staff=staff, start=now, end=now, name='テスト')
        response = self.client.get(resolve_url('booking:my_page_day_detail', pk=staff.pk, year=now.year, month=now.month, day=now.day))
        self.assertContains(response, 'テスト')

    def test_one_schedule_23(self):
        """時間外の予約は表示されないことを確認"""
        self.client.login(username='tanakataro', password='helloworld123')
        staff = get_object_or_404(Staff, pk=1)
        now = timezone.localtime().replace(hour=23, minute=0, second=0)
        Schedule.objects.create(staff=staff, start=now, end=now, name='テスト')
        response = self.client.get(resolve_url('booking:my_page_day_detail', pk=staff.pk, year=now.year, month=now.month, day=now.day))
        self.assertNotContains(response, 'テスト')


class MyPageScheduleViewTests(TestCase):
    fixtures = ['initial']

    def test_anonymous(self):
        """ログインしていないと403"""
        now = timezone.now()
        staff = get_object_or_404(Staff, pk=1)
        s1 = Schedule.objects.create(staff=staff, start=now, end=now, name='テスト')
        response = self.client.get(resolve_url('booking:my_page_schedule', pk=s1.pk))
        self.assertEqual(response.status_code, 403)

    def test_login_admin(self):
        """管理者は誰の予約でも詳細ページが見れる"""
        self.client.login(username='admin', password='admin123')
        now = timezone.now()
        staff = get_object_or_404(Staff, pk=1)
        s1 = Schedule.objects.create(staff=staff, start=now, end=now, name='テスト')
        response = self.client.get(resolve_url('booking:my_page_schedule', pk=s1.pk))
        self.assertContains(response, '店舗A店 ぱいそん')

    def test_login_tanaka(self):
        """自分担当の予約は、詳細ページが見れる"""
        self.client.login(username='tanakataro', password='helloworld123')
        now = timezone.now()
        staff = get_object_or_404(Staff, pk=1)
        s1 = Schedule.objects.create(staff=staff, start=now, end=now, name='テスト')
        response = self.client.get(resolve_url('booking:my_page_schedule', pk=s1.pk))
        self.assertContains(response, '店舗A店 ぱいそん')

    def test_login_yosida(self):
        """自分の担当じゃない予約は、詳細ページが見れない(403)"""
        self.client.login(username='yosidaziro', password='helloworld123')
        now = timezone.now()
        staff = get_object_or_404(Staff, pk=1)
        s1 = Schedule.objects.create(staff=staff, start=now, end=now, name='テスト')
        response = self.client.get(resolve_url('booking:my_page_schedule', pk=s1.pk))
        self.assertEqual(response.status_code, 403)

    def test_post(self):
        """予約の更新を行い、反映されるかのテスト"""
        self.client.login(username='tanakataro', password='helloworld123')
        now = timezone.now() + datetime.timedelta(days=1)
        staff = get_object_or_404(Staff, pk=1)
        s1 = Schedule.objects.create(staff=staff, start=now, end=now, name='テスト')
        now_str = now.strftime('%Y-%m-%d %H:%M:%S')
        response = self.client.post(
            resolve_url('booking:my_page_schedule', pk=s1.pk),
            {'name': '更新しました', 'start': now_str, 'end': now_str},
            follow=True
        )
        self.assertEqual(list(response.context['schedule_list']), [s1])


class MyPageScheduleDeleteViewTests(TestCase):
    fixtures = ['initial']

    def test_get(self):
        """予約の削除ページ。GETアクセスは想定していないので、TemplateDoesNotExist"""
        self.client.login(username='tanakataro', password='helloworld123')
        now = timezone.now() + datetime.timedelta(days=1)
        staff = get_object_or_404(Staff, pk=1)
        s1 = Schedule.objects.create(staff=staff, start=now, end=now, name='テスト')
        with self.assertRaises(TemplateDoesNotExist):
            response = self.client.get(resolve_url('booking:my_page_schedule_delete', pk=s1.pk),)

    def test_post(self):
        """予約を削除すると当然、マイページの一覧には表示されなくなる"""
        self.client.login(username='tanakataro', password='helloworld123')
        now = timezone.now() + datetime.timedelta(days=1)
        staff = get_object_or_404(Staff, pk=1)
        s1 = Schedule.objects.create(staff=staff, start=now, end=now, name='テスト')
        response = self.client.post(
            resolve_url('booking:my_page_schedule_delete', pk=s1.pk),
            follow=True
        )
        self.assertEqual(list(response.context['schedule_list']), [])


class MyPageHolidayAddViewTests(TestCase):
    fixtures = ['initial']

    def test_anonymous(self):
        """ログインしていないと403"""
        now = timezone.now()
        staff = get_object_or_404(Staff, pk=1)
        response = self.client.post(
            resolve_url('booking:my_page_holiday_add', pk=staff.pk, year=now.year, month=now.month, day=now.day, hour=9),
            follow=True,
        )
        self.assertEqual(response.status_code, 403)

    def test_login_admin(self):
        """スーパーユーザーは、休日追加を自由に行える"""
        self.client.login(username='admin', password='admin123')
        now = timezone.now()
        staff = get_object_or_404(Staff, pk=1)
        response = self.client.post(
            resolve_url('booking:my_page_holiday_add', pk=staff.pk, year=now.year, month=now.month, day=now.day, hour=9),
            follow=True,
        )
        self.assertContains(response, '休暇(システムによる追加)')
        self.assertEqual(response.status_code, 200)

    def test_login_tanaka(self):
        """自分で休日を追加できることを確認"""
        self.client.login(username='tanakataro', password='helloworld123')
        now = timezone.now()
        staff = get_object_or_404(Staff, pk=1)
        response = self.client.post(
            resolve_url('booking:my_page_holiday_add', pk=staff.pk, year=now.year, month=now.month, day=now.day, hour=9),
            follow=True,
        )
        self.assertContains(response, '休暇(システムによる追加)')
        self.assertEqual(response.status_code, 200)

    def test_login_yosida(self):
        """他人の休日は追加できないことを確認"""
        self.client.login(username='yosidaziro', password='helloworld123')
        now = timezone.now()
        staff = get_object_or_404(Staff, pk=1)
        response = self.client.post(
            resolve_url('booking:my_page_holiday_add', pk=staff.pk, year=now.year, month=now.month, day=now.day, hour=9),
            follow=True,
        )
        self.assertEqual(response.status_code, 403)

    def test_get(self):
        """GETでアクセスできないことを確認"""
        self.client.login(username='admin', password='admin123')
        now = timezone.now()
        staff = get_object_or_404(Staff, pk=1)
        response = self.client.get(
            resolve_url('booking:my_page_holiday_add', pk=staff.pk, year=now.year, month=now.month, day=now.day, hour=9),
            follow=True,
        )
        self.assertEqual(response.status_code, 405)



class SeatBoardViewTests(TestCase):
    fixtures = ['initial']

    def setUp(self):
        from .models import Seat, Store
        self.store = Store.objects.get(pk=1)
        self.seat = Seat.objects.create(store=self.store, name='T1', capacity=4)

    def test_requires_store_membership(self):
        self.client.login(username='yosidaziro', password='helloworld123')
        response = self.client.get(resolve_url('booking:seat_board', pk=2))
        self.assertEqual(response.status_code, 403)

    def test_board_shows_seat_and_reservation(self):
        staff = get_object_or_404(Staff, pk=1)
        now = timezone.localtime().replace(hour=10, minute=0, second=0, microsecond=0)
        Schedule.objects.create(
            staff=staff, start=now, end=now + datetime.timedelta(hours=1),
            name='佐藤', seat=self.seat, party_size=3,
        )
        self.client.login(username='tanakataro', password='helloworld123')
        response = self.client.get(resolve_url('booking:seat_board', pk=1))
        self.assertContains(response, 'T1')
        self.assertContains(response, '佐藤(3名)')

    def test_walkin_start_and_end(self):
        from .models import WalkIn
        self.client.login(username='tanakataro', password='helloworld123')
        response = self.client.post(
            resolve_url('booking:walkin_start', seat_pk=self.seat.pk),
            {'party_size': '2'}, follow=True,
        )
        walkin = WalkIn.objects.get(seat=self.seat)
        self.assertTrue(walkin.is_active)
        self.assertEqual(walkin.party_size, 2)

        # 使用中の席には重ねて着席できない
        response = self.client.post(
            resolve_url('booking:walkin_start', seat_pk=self.seat.pk),
            {'party_size': '1'}, follow=True,
        )
        messages = [str(m) for m in response.context['messages']]
        self.assertIn('T1 は使用中です。', messages)

        self.client.post(resolve_url('booking:walkin_end', pk=walkin.pk))
        walkin.refresh_from_db()
        self.assertFalse(walkin.is_active)

    def test_seat_double_booking_rejected(self):
        from django.db import IntegrityError
        staff1 = get_object_or_404(Staff, pk=1)
        staff3 = get_object_or_404(Staff, pk=3)
        now = timezone.localtime().replace(hour=10, minute=0, second=0, microsecond=0)
        Schedule.objects.create(
            staff=staff1, start=now, end=now + datetime.timedelta(hours=1), name='A', seat=self.seat,
        )
        with self.assertRaises(IntegrityError):
            Schedule.objects.create(
                staff=staff3, start=now, end=now + datetime.timedelta(hours=1), name='B', seat=self.seat,
            )


class ModelConstraintTests(TestCase):
    fixtures = ['initial']

    def test_store_rejects_overnight_hours(self):
        from django.db import IntegrityError
        from .models import Store
        with self.assertRaises(IntegrityError):
            Store.objects.create(name='深夜バー', opening_hour=18, closing_hour=2)

    def test_store_allows_late_night_closing(self):
        from .models import Store
        store = Store.objects.create(name='26時閉店', opening_hour=18, closing_hour=26)
        self.assertEqual(list(store.business_hours), list(range(18, 26)))

    def test_store_rejects_hours_beyond_30(self):
        from django.db import IntegrityError
        from .models import Store
        with self.assertRaises(IntegrityError):
            Store.objects.create(name='31時閉店', opening_hour=18, closing_hour=31)

    def test_store_rejects_span_over_24_hours(self):
        # 営業24時間超は翌日早朝の枠がどの営業日か曖昧になるため禁止
        from django.db import IntegrityError
        from .models import Store
        with self.assertRaises(IntegrityError):
            Store.objects.create(name='ほぼ無休', opening_hour=1, closing_hour=26)

    def test_single_active_walkin_per_seat(self):
        from django.db import IntegrityError, transaction
        from .models import Seat, Store, WalkIn
        store = Store.objects.get(pk=1)
        seat = Seat.objects.create(store=store, name='T9')
        WalkIn.objects.create(seat=seat, party_size=2)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                WalkIn.objects.create(seat=seat, party_size=1)
        # 離席後は再度着席できる
        active = WalkIn.objects.get(seat=seat)
        active.left_at = timezone.now()
        active.save()
        WalkIn.objects.create(seat=seat, party_size=3)


class ManagerRoleTests(TestCase):
    """承認系操作は店長(is_manager)限定であることの確認。

    fixture: tanakataro のスタッフ(pk=1,2)は店長、yosidaziro のスタッフ(pk=3)は一般。
    """
    fixtures = ['initial']

    def test_non_manager_cannot_open_store(self):
        self.client.login(username='yosidaziro', password='helloworld123')
        response = self.client.post(resolve_url('operations:open_store', store_pk=1))
        self.assertEqual(response.status_code, 403)

    def test_manager_can_open_store(self):
        self.client.login(username='tanakataro', password='helloworld123')
        response = self.client.post(resolve_url('operations:open_store', store_pk=1), follow=True)
        self.assertEqual(response.status_code, 200)

    def test_non_manager_cannot_approve_sns_draft(self):
        import tempfile
        from django.test import override_settings
        with override_settings(MEDIA_ROOT=tempfile.mkdtemp()):
            from sns import services as sns_services
            from .models import Store
            draft = sns_services.generate_draft(Store.objects.get(pk=1), timezone.localdate())
        self.client.login(username='yosidaziro', password='helloworld123')
        response = self.client.post(resolve_url('sns:approve', pk=draft.pk))
        self.assertEqual(response.status_code, 403)

    def test_non_manager_can_still_view_dashboard_and_toggle_tasks(self):
        # 一般スタッフ(キャスト)もダッシュボード閲覧とチェックリスト操作はできる
        self.client.login(username='yosidaziro', password='helloworld123')
        response = self.client.get(resolve_url('operations:dashboard', store_pk=1))
        self.assertEqual(response.status_code, 200)


class DatabaseUrlParserTests(TestCase):
    def test_standard_url(self):
        from project.database import database_config_from_url
        config = database_config_from_url('postgres://app:s3cret@10.0.0.5:5432/booking')
        self.assertEqual(config['ENGINE'], 'django.db.backends.postgresql')
        self.assertEqual(config['NAME'], 'booking')
        self.assertEqual(config['USER'], 'app')
        self.assertEqual(config['PASSWORD'], 's3cret')
        self.assertEqual(config['HOST'], '10.0.0.5')
        self.assertEqual(config['PORT'], '5432')

    def test_cloud_sql_unix_socket(self):
        from project.database import database_config_from_url
        config = database_config_from_url(
            'postgres://app:pw@/booking?host=/cloudsql/myproj:asia-northeast1:db1'
        )
        self.assertEqual(config['HOST'], '/cloudsql/myproj:asia-northeast1:db1')
        self.assertEqual(config['NAME'], 'booking')

    def test_rejects_unknown_scheme(self):
        from django.core.exceptions import ImproperlyConfigured
        from project.database import database_config_from_url
        with self.assertRaises(ImproperlyConfigured):
            database_config_from_url('mysql://a:b@h/db')


class LateNightBusinessTests(TestCase):
    """深夜営業(閉店が翌日にまたがる店)のカレンダー・予約・座席ボード。"""
    fixtures = ['initial']

    def setUp(self):
        from .models import Store
        # 店舗Aを 18時-翌2時 営業に変更
        self.store = Store.objects.get(pk=1)
        self.store.opening_hour = 18
        self.store.closing_hour = 26
        self.store.save()

    def test_make_aware_datetime_rolls_over_midnight(self):
        from .views import make_aware_datetime
        dt = make_aware_datetime(2026, 9, 1, 25)
        local = timezone.localtime(dt)
        self.assertEqual((local.month, local.day, local.hour), (9, 2, 1))

    def test_business_slot_maps_early_morning_to_previous_day(self):
        from .views import make_aware_datetime
        local = timezone.localtime(make_aware_datetime(2026, 9, 1, 25))
        slot_date, slot_hour = self.store.business_slot(local)
        self.assertEqual((slot_date, slot_hour), (datetime.date(2026, 9, 1), 25))
        # 営業日当日の通常時刻はそのまま
        local = timezone.localtime(make_aware_datetime(2026, 9, 1, 19))
        self.assertEqual(self.store.business_slot(local), (datetime.date(2026, 9, 1), 19))

    def test_calendar_shows_late_night_rows_and_bookings(self):
        from .views import make_aware_datetime
        staff = get_object_or_404(Staff, pk=1)
        base = timezone.localdate() + datetime.timedelta(days=1)
        # 翌1時(=25時枠)の予約を入れる
        start = make_aware_datetime(base.year, base.month, base.day, 25)
        Schedule.objects.create(staff=staff, start=start, end=start + datetime.timedelta(hours=1), name='深夜客')
        response = self.client.get(
            resolve_url('booking:calendar', pk=1, year=base.year, month=base.month, day=base.day)
        )
        self.assertContains(response, '25:00')  # 深夜枠の行が表示される
        self.assertContains(response, batu)     # 25時枠が×になっている

    def test_booking_at_hour_25_creates_next_day_schedule(self):
        base = timezone.localdate() + datetime.timedelta(days=1)
        response = self.client.post(
            resolve_url('booking:booking', pk=1, year=base.year, month=base.month, day=base.day, hour=25),
            {'name': '深夜予約'}, follow=True,
        )
        self.assertEqual(response.status_code, 200)
        schedule = Schedule.objects.get(name='深夜予約')
        local = timezone.localtime(schedule.start)
        self.assertEqual(local.date(), base + datetime.timedelta(days=1))
        self.assertEqual(local.hour, 1)

    def test_seat_board_shows_late_night_reservation(self):
        from .models import Seat
        from .views import make_aware_datetime
        seat = Seat.objects.create(store=self.store, name='VIP1', capacity=4)
        staff = get_object_or_404(Staff, pk=1)
        today = timezone.localdate()
        start = make_aware_datetime(today.year, today.month, today.day, 25)
        Schedule.objects.create(
            staff=staff, start=start, end=start + datetime.timedelta(hours=1),
            name='深夜卓', seat=seat, party_size=2,
        )
        self.client.login(username='tanakataro', password='helloworld123')
        response = self.client.get(resolve_url('booking:seat_board', pk=1))
        self.assertContains(response, '25:00')
        self.assertContains(response, '深夜卓(2名)')


class GbpPayloadTests(TestCase):
    fixtures = ['initial']

    def test_overnight_special_hours_payload(self):
        from booking.models import Store
        from operations.gbp import special_hours_payload
        from operations.models import BusinessDay
        store = Store.objects.get(pk=1)
        business_day = BusinessDay(store=store, date=datetime.date(2026, 12, 31),
                                   opening_hour_override=18, closing_hour_override=26)
        period = special_hours_payload(business_day)['specialHours']['specialHourPeriods'][0]
        self.assertEqual(period['startDate']['day'], 31)
        self.assertEqual(period['openTime'], {'hours': 18})
        self.assertEqual(period['endDate'], {'year': 2027, 'month': 1, 'day': 1})
        self.assertEqual(period['closeTime'], {'hours': 2})

    def test_same_day_payload_has_no_end_date(self):
        from booking.models import Store
        from operations.gbp import special_hours_payload
        from operations.models import BusinessDay
        store = Store.objects.get(pk=1)
        business_day = BusinessDay(store=store, date=datetime.date(2026, 9, 1), closing_hour_override=15)
        period = special_hours_payload(business_day)['specialHours']['specialHourPeriods'][0]
        self.assertNotIn('endDate', period)
        self.assertEqual(period['closeTime'], {'hours': 15})


class FeatureFlagTests(TestCase):
    """店舗ごとの機能フラグ。オフの機能は404になり、開店連鎖からも除外される。"""
    fixtures = ['initial']

    def setUp(self):
        from .models import Store
        self.store = Store.objects.get(pk=1)
        self.client.login(username='tanakataro', password='helloworld123')

    def _open_store(self):
        import tempfile
        from django.test import override_settings
        from operations import services as ops
        with override_settings(MEDIA_ROOT=tempfile.mkdtemp()):
            business_day = ops.start_business_day(self.store, timezone.localdate())
            ops.open_store(business_day)
        return business_day

    def test_sns_disabled_hides_views_and_skips_generation(self):
        self.store.enable_sns = False
        self.store.save()
        response = self.client.get(resolve_url('sns:draft_list', store_pk=1))
        self.assertEqual(response.status_code, 404)

        business_day = self._open_store()
        from sns.models import PostDraft
        self.assertFalse(PostDraft.objects.filter(store=self.store).exists())
        self.assertFalse(business_day.tasks.filter(title__contains='SNS').exists())
        # 開店自体は成功している
        self.assertEqual(business_day.status, 'open')

    def test_inventory_disabled_hides_views_and_skips_tasks(self):
        from inventory.models import Product, StockMovement
        self.store.enable_inventory = False
        self.store.save()
        response = self.client.get(resolve_url('inventory:stock_list', store_pk=1))
        self.assertEqual(response.status_code, 404)

        product = Product.objects.create(store=self.store, name='入荷品', reorder_point=5)
        StockMovement.objects.create(product=product, kind=StockMovement.KIND_ARRIVAL, quantity=3)
        business_day = self._open_store()
        self.assertFalse(business_day.tasks.filter(title__contains='品出し').exists())
        self.assertFalse(business_day.tasks.filter(title__contains='発注案').exists())

    def test_seat_board_disabled_returns_404(self):
        self.store.enable_seat_board = False
        self.store.save()
        response = self.client.get(resolve_url('booking:seat_board', pk=1))
        self.assertEqual(response.status_code, 404)

    def test_gbp_disabled_skips_reminder(self):
        import tempfile
        from django.test import override_settings
        from operations import services as ops
        self.store.enable_gbp = False
        self.store.save()
        with override_settings(MEDIA_ROOT=tempfile.mkdtemp()):
            business_day = ops.start_business_day(self.store, timezone.localdate())
            business_day.opening_hour_override = 12
            business_day.save()
            ops.open_store(business_day)
        self.assertFalse(business_day.tasks.filter(title__contains='Googleビジネスプロフィール').exists())

    def test_flags_default_on(self):
        # デフォルトは全機能ON(既存店舗の挙動を変えない)
        from .models import Store
        store = Store.objects.create(name='新店', opening_hour=10, closing_hour=20)
        self.assertTrue(store.enable_sns)
        self.assertTrue(store.enable_inventory)
        self.assertTrue(store.enable_seat_board)
        self.assertTrue(store.enable_gbp)
