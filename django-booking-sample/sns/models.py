from django.conf import settings
from django.db import models
from django.utils import timezone

from booking.models import Store

DEFAULT_BODY_TEMPLATE = (
    '【{store_name}】{date} 本日オープン!\n'
    '{casts_section}'
    '{arrivals_section}'
    'ご来店お待ちしております!'
)


class PostTemplate(models.Model):
    """SNS投稿の文面テンプレート(店舗ごとに管理画面で編集)。

    使えるプレースホルダ:
    {store_name} {date} {casts} {casts_section} {arrivals} {arrivals_section}
    """
    store = models.ForeignKey(Store, verbose_name='店舗', on_delete=models.CASCADE, related_name='post_templates')
    name = models.CharField('テンプレート名', max_length=50, default='開店告知')
    body = models.TextField('本文テンプレート', default=DEFAULT_BODY_TEMPLATE)
    is_active = models.BooleanField('有効', default=True)

    def __str__(self):
        return f'{self.store.name}: {self.name}'


class PostDraft(models.Model):
    """SNS投稿の下書き。生成は自動、確定(承認)は必ず人間が行う。"""
    STATUS_DRAFT = 'draft'
    STATUS_APPROVED = 'approved'
    STATUS_CHOICES = [
        (STATUS_DRAFT, '下書き(承認待ち)'),
        (STATUS_APPROVED, '承認済み'),
    ]

    store = models.ForeignKey(Store, verbose_name='店舗', on_delete=models.CASCADE, related_name='post_drafts')
    date = models.DateField('対象日')
    body = models.TextField('本文')
    image = models.ImageField('画像', upload_to='sns/', blank=True)
    status = models.CharField('状態', max_length=10, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    created_at = models.DateTimeField('作成', auto_now_add=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='承認者', on_delete=models.SET_NULL, null=True, blank=True
    )
    approved_at = models.DateTimeField('承認時刻', null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            # 同日の下書きは1件のみ(承認済みの日に再生成して二重投稿する事故の防止)
            models.UniqueConstraint(fields=['store', 'date'], name='unique_post_draft_per_day'),
        ]

    def __str__(self):
        return f'{self.store.name} {self.date} ({self.get_status_display()})'

    def approve(self, user):
        self.status = self.STATUS_APPROVED
        self.approved_by = user
        self.approved_at = timezone.now()
        self.save(update_fields=['status', 'approved_by', 'approved_at'])


class PostResult(models.Model):
    """プラットフォームごとの投稿結果。manual は手動コピペ投稿へのフォールバック。"""
    STATUS_POSTED = 'posted'
    STATUS_FAILED = 'failed'
    STATUS_MANUAL = 'manual'
    STATUS_CHOICES = [
        (STATUS_POSTED, '投稿済み'),
        (STATUS_FAILED, '失敗'),
        (STATUS_MANUAL, '手動投稿してください'),
    ]

    draft = models.ForeignKey(PostDraft, verbose_name='下書き', on_delete=models.CASCADE, related_name='results')
    platform = models.CharField('プラットフォーム', max_length=20)
    status = models.CharField('状態', max_length=10, choices=STATUS_CHOICES)
    external_url = models.URLField('投稿URL', blank=True)
    detail = models.CharField('詳細', max_length=255, blank=True)
    created_at = models.DateTimeField('日時', auto_now_add=True)

    class Meta:
        ordering = ['platform', '-created_at']

    def __str__(self):
        return f'{self.draft} [{self.platform}] {self.get_status_display()}'
