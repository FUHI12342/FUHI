from django.dispatch import receiver

from . import gbp
from .models import ChecklistTask
from .signals import store_opened


@receiver(store_opened, dispatch_uid='operations_gbp_sync_on_open')
def sync_gbp_on_open(sender, business_day, user=None, **kwargs):
    """臨時営業時間があるときだけ GBP を更新する。

    - API設定済み → specialHours を自動反映(失敗は open_store が警告タスク化)
    - 未設定 → 手動更新のリマインダータスクに格下げ(毎日は出さない。変更がある日だけ)
    """
    has_override = (
        business_day.opening_hour_override is not None
        or business_day.closing_hour_override is not None
    )
    if not has_override:
        return

    if gbp.is_configured():
        gbp.sync_special_hours(business_day)
        return

    ChecklistTask.objects.get_or_create(
        business_day=business_day,
        title=(
            f'Googleビジネスプロフィールの営業時間を手動更新する'
            f'(本日 {business_day.opening_hour}時-{business_day.closing_hour}時)'
        ),
        defaults={'order': 930},
    )
