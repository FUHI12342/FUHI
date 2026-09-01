import logging

from django.utils import timezone

from attendance.models import confirm_shifts
from .models import BusinessDay, ChecklistTask
from .signals import store_opened

logger = logging.getLogger(__name__)


def start_business_day(store, date):
    """営業日を取得(なければ作成)し、チェックリストを雛形から生成する。"""
    business_day, created = BusinessDay.objects.get_or_create(store=store, date=date)
    if created or not business_day.tasks.exists():
        items = store.checklist_template.filter(is_active=True)
        ChecklistTask.objects.bulk_create([
            ChecklistTask(business_day=business_day, title=item.title, order=item.order)
            for item in items
        ])
    return business_day


def open_store(business_day, user=None):
    """開店操作。シフト確定と自動処理(SNS投稿キュー等)を連鎖実行する。

    シグナルレシーバの例外は開店操作全体を止めず、警告タスクとして
    チェックリストに載せる(自動化の失敗を人間が検知する場所)。
    """
    if business_day.status == BusinessDay.STATUS_OPEN:
        return business_day

    confirmed = confirm_shifts(business_day.store, business_day.date)
    logger.info('confirmed %s shifts for %s', confirmed, business_day)

    responses = store_opened.send_robust(sender=None, business_day=business_day, user=user)
    for receiver, response in responses:
        if isinstance(response, Exception):
            name = getattr(receiver, '__name__', repr(receiver))
            logger.exception('store_opened receiver %s failed', name, exc_info=response)
            ChecklistTask.objects.create(
                business_day=business_day,
                title=f'自動処理の失敗を確認: {name}',
                order=999,
                alert=str(response)[:255],
            )

    business_day.status = BusinessDay.STATUS_OPEN
    business_day.opened_at = timezone.now()
    business_day.save(update_fields=['status', 'opened_at'])
    return business_day


def close_store(business_day):
    """閉店操作。"""
    if business_day.status != BusinessDay.STATUS_CLOSED:
        business_day.status = BusinessDay.STATUS_CLOSED
        business_day.closed_at = timezone.now()
        business_day.save(update_fields=['status', 'closed_at'])
    return business_day
