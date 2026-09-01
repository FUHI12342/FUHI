from django.dispatch import receiver

from operations.models import ChecklistTask
from operations.signals import store_opened

from . import services


@receiver(store_opened, dispatch_uid='sns_generate_draft_on_open')
def generate_draft_on_open(sender, business_day, user=None, **kwargs):
    """開店操作をトリガーに SNS 下書きを生成し、承認タスクをチェックリストに載せる。

    投稿の確定は必ず人間の承認操作(sns:draft_detail)で行う。ここでは生成まで。
    """
    if not business_day.store.enable_sns:
        return
    services.generate_draft(business_day.store, business_day.date)
    ChecklistTask.objects.get_or_create(
        business_day=business_day,
        title='SNS投稿の下書きを確認して承認する',
        defaults={'order': 900},
    )
