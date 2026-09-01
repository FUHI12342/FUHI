import datetime
import tempfile

from django.shortcuts import resolve_url
from django.test import TestCase, override_settings
from django.utils import timezone

from attendance.models import Shift
from booking.models import Staff, Store
from operations import services as ops_services
from .adapters import AdapterError, BaseAdapter
from .models import PostDraft, PostResult, PostTemplate
from . import services

MEDIA_TMP = tempfile.mkdtemp()


def make_cast_shift(staff, date, publishable=True):
    staff.sns_publishable = publishable
    staff.kind = Staff.KIND_CAST
    staff.save()
    return Shift.objects.create(
        staff=staff, date=date,
        start_time=datetime.time(18, 0), end_time=datetime.time(23, 0),
    )


class FakeAdapter(BaseAdapter):
    platform = 'fake'

    def __init__(self, configured=True, fail=False):
        self.configured = configured
        self.fail = fail

    def is_configured(self):
        return self.configured

    def publish(self, body, image_url=None):
        if self.fail:
            raise AdapterError('boom')
        return 'https://example.com/post/1'


class BuildBodyTests(TestCase):
    fixtures = ['initial']

    def setUp(self):
        self.store = Store.objects.get(pk=1)
        self.today = timezone.localdate()

    def test_default_template_with_casts_and_arrivals(self):
        shift = make_cast_shift(Staff.objects.get(pk=1), self.today)
        body = services.build_body(self.store, self.today, [shift], ['新酒「初雪」'])
        self.assertIn('店舗A', body)
        self.assertIn('ぱいそん(18:00〜)', body)
        self.assertIn('入荷情報: 新酒「初雪」', body)

    def test_no_casts_no_arrivals_sections_omitted(self):
        body = services.build_body(self.store, self.today, [], [])
        self.assertNotIn('本日の出勤', body)
        self.assertNotIn('入荷情報', body)

    def test_broken_template_falls_back_to_default(self):
        PostTemplate.objects.create(store=self.store, body='{unknown_placeholder}')
        body = services.build_body(self.store, self.today, [], [])
        self.assertIn('店舗A', body)


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class GenerateDraftTests(TestCase):
    fixtures = ['initial']

    def setUp(self):
        self.store = Store.objects.get(pk=1)
        self.today = timezone.localdate()

    def test_only_publishable_casts_included(self):
        make_cast_shift(Staff.objects.get(pk=1), self.today, publishable=True)
        make_cast_shift(Staff.objects.get(pk=3), self.today, publishable=False)
        draft = services.generate_draft(self.store, self.today)
        self.assertIn('ぱいそん', draft.body)
        self.assertNotIn('じゃば', draft.body)
        self.assertTrue(draft.image.name)

    def test_regenerate_updates_same_draft(self):
        draft1 = services.generate_draft(self.store, self.today)
        draft2 = services.generate_draft(self.store, self.today)
        self.assertEqual(draft1.pk, draft2.pk)

    def test_regenerate_after_approval_does_not_create_second_draft(self):
        # 承認済みの日に再生成しても新しい下書きは作られない(同日の二重投稿防止)
        draft = services.generate_draft(self.store, self.today)
        user = Staff.objects.get(pk=1).user
        services.publish_draft(draft, user, adapters=[])
        body_before = PostDraft.objects.get(pk=draft.pk).body
        again = services.generate_draft(self.store, self.today)
        self.assertEqual(again.pk, draft.pk)
        self.assertEqual(PostDraft.objects.filter(store=self.store, date=self.today).count(), 1)
        self.assertEqual(again.status, PostDraft.STATUS_APPROVED)
        self.assertEqual(again.body, body_before)


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class PublishDraftTests(TestCase):
    fixtures = ['initial']

    def setUp(self):
        self.store = Store.objects.get(pk=1)
        self.today = timezone.localdate()
        self.draft = services.generate_draft(self.store, self.today)
        self.user = Staff.objects.get(pk=1).user

    def test_unconfigured_adapter_falls_back_to_manual(self):
        results = services.publish_draft(self.draft, self.user, adapters=[FakeAdapter(configured=False)])
        self.assertEqual(results[0].status, PostResult.STATUS_MANUAL)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, PostDraft.STATUS_APPROVED)

    def test_configured_adapter_posts(self):
        results = services.publish_draft(self.draft, self.user, adapters=[FakeAdapter()])
        self.assertEqual(results[0].status, PostResult.STATUS_POSTED)
        self.assertEqual(results[0].external_url, 'https://example.com/post/1')

    def test_failed_adapter_records_failure(self):
        results = services.publish_draft(self.draft, self.user, adapters=[FakeAdapter(fail=True)])
        self.assertEqual(results[0].status, PostResult.STATUS_FAILED)
        self.assertIn('boom', results[0].detail)

    def test_raw_exception_does_not_abort_publish_loop(self):
        # AdapterError 以外の例外(実APIの生のネットワーク例外等)でも
        # 失敗として記録し、後続プラットフォームの配信を続行する
        class RawErrorAdapter(FakeAdapter):
            platform = 'raw'

            def publish(self, body, image_url=None):
                raise ValueError('connection reset')

        results = services.publish_draft(
            self.draft, self.user, adapters=[RawErrorAdapter(), FakeAdapter()]
        )
        self.assertEqual(results[0].status, PostResult.STATUS_FAILED)
        self.assertEqual(results[1].status, PostResult.STATUS_POSTED)

    def test_retry_unfinished_targets_failed_and_missing_only(self):
        failed = FakeAdapter(fail=True)
        services.publish_draft(self.draft, self.user, adapters=[failed])
        # 再試行: 今度は成功するアダプタ + 未記録のプラットフォーム
        ok = FakeAdapter()
        missing = FakeAdapter()
        missing.platform = 'missing'
        results = services.retry_unfinished(self.draft, adapters=[ok, missing])
        self.assertEqual({r.platform for r in results}, {'fake', 'missing'})
        self.assertTrue(all(r.status == PostResult.STATUS_POSTED for r in results))
        # 投稿済みになった後の再試行は何もしない(二重投稿防止)
        self.assertEqual(services.retry_unfinished(self.draft, adapters=[ok]), [])


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class OpenStoreIntegrationTests(TestCase):
    fixtures = ['initial']

    def test_open_store_generates_draft_and_checklist_task(self):
        store = Store.objects.get(pk=1)
        today = timezone.localdate()
        make_cast_shift(Staff.objects.get(pk=1), today)
        business_day = ops_services.start_business_day(store, today)
        ops_services.open_store(business_day)

        draft = PostDraft.objects.get(store=store, date=today)
        self.assertIn('ぱいそん', draft.body)
        self.assertTrue(
            business_day.tasks.filter(title='SNS投稿の下書きを確認して承認する').exists()
        )
        # 自動処理は生成まで。無人で投稿(承認)はしない。
        self.assertEqual(draft.status, PostDraft.STATUS_DRAFT)


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class DraftViewTests(TestCase):
    fixtures = ['initial']

    def setUp(self):
        self.store = Store.objects.get(pk=1)
        self.today = timezone.localdate()

    def test_list_requires_membership(self):
        self.client.login(username='yosidaziro', password='helloworld123')
        response = self.client.get(resolve_url('sns:draft_list', store_pk=2))
        self.assertEqual(response.status_code, 403)

    def test_approve_flow(self):
        draft = services.generate_draft(self.store, self.today)
        self.client.login(username='tanakataro', password='helloworld123')
        response = self.client.post(resolve_url('sns:approve', pk=draft.pk), follow=True)
        self.assertContains(response, '承認しました')
        draft.refresh_from_db()
        self.assertEqual(draft.status, PostDraft.STATUS_APPROVED)
        # 実APIは未設定なので全プラットフォームが手動フォールバックになる
        statuses = set(draft.results.values_list('status', flat=True))
        self.assertEqual(statuses, {PostResult.STATUS_MANUAL})

    def test_approve_twice_does_not_duplicate_manual_results(self):
        # 全プラットフォームが manual(担当は人間)の場合、再POSTは何も再配信しない
        draft = services.generate_draft(self.store, self.today)
        self.client.login(username='tanakataro', password='helloworld123')
        self.client.post(resolve_url('sns:approve', pk=draft.pk))
        count = draft.results.count()
        response = self.client.post(resolve_url('sns:approve', pk=draft.pk), follow=True)
        self.assertContains(response, '再配信が必要なプラットフォームはありません')
        self.assertEqual(draft.results.count(), count)
