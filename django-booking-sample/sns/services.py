import logging

from django.core.files.base import ContentFile

from attendance.models import Shift
from .adapters import AdapterError, get_adapters
from .imaging import generate_open_image
from .models import DEFAULT_BODY_TEMPLATE, PostDraft, PostResult, PostTemplate

logger = logging.getLogger(__name__)


def _arrivals_for(store, date):
    """入荷情報(Phase 3 の inventory アプリが提供)。未導入なら空。"""
    try:
        from inventory.services import sns_arrivals
    except ImportError:
        return []
    return sns_arrivals(store, date)


def build_body(store, date, cast_shifts, arrivals):
    template = PostTemplate.objects.filter(store=store, is_active=True).first()
    body_template = template.body if template else DEFAULT_BODY_TEMPLATE

    casts = '、'.join(shift.staff.name for shift in cast_shifts)
    casts_section = ''
    if casts:
        lines = '\n'.join(
            f'・{shift.staff.name}({shift.start_time:%H:%M}〜)' for shift in cast_shifts
        )
        casts_section = f'\n本日の出勤\n{lines}\n\n'

    arrivals_text = '、'.join(arrivals)
    arrivals_section = f'\n入荷情報: {arrivals_text}\n\n' if arrivals_text else ''

    context = {
        'store_name': store.name,
        'date': f'{date:%m/%d}',
        'casts': casts,
        'casts_section': casts_section,
        'arrivals': arrivals_text,
        'arrivals_section': arrivals_section,
    }
    try:
        return body_template.format(**context)
    except (KeyError, IndexError, ValueError) as e:
        logger.warning('post template for %s is broken (%s); falling back to default', store, e)
        return DEFAULT_BODY_TEMPLATE.format(**context)


def generate_draft(store, date):
    """開店告知の下書き(文面+画像)を生成する。1日1件、再生成は上書き。

    出勤キャストは publishable_casts(在籍中・SNS掲載可)のみを使う。
    """
    cast_shifts = list(Shift.objects.publishable_casts(store, date))
    arrivals = _arrivals_for(store, date)
    body = build_body(store, date, cast_shifts, arrivals)

    draft, _created = PostDraft.objects.update_or_create(
        store=store, date=date, status=PostDraft.STATUS_DRAFT,
        defaults={'body': body},
    )
    png = generate_open_image(store.name, date, cast_shifts)
    draft.image.save(f'{store.pk}_{date:%Y%m%d}.png', ContentFile(png), save=True)
    return draft


def publish_draft(draft, user, adapters=None):
    """承認済みにして各プラットフォームへ配信する。

    - 未設定のプラットフォーム → manual(文面と画像を人間がコピペ投稿)
    - API失敗 → failed(承認は維持。再試行 or 手動投稿)
    """
    draft.approve(user)
    if adapters is None:
        adapters = get_adapters()

    image_url = None
    if draft.image:
        # 公開URLが必要(Instagram)。MEDIA が公開ホスティングされている場合のみ意味を持つ。
        base = _public_media_base()
        if base:
            image_url = base.rstrip('/') + draft.image.url

    results = []
    for adapter in adapters:
        if not adapter.is_configured():
            results.append(PostResult.objects.create(
                draft=draft, platform=adapter.platform, status=PostResult.STATUS_MANUAL,
                detail='API未設定のため、文面と画像をコピーして手動投稿してください。',
            ))
            continue
        try:
            url = adapter.publish(draft.body, image_url)
            results.append(PostResult.objects.create(
                draft=draft, platform=adapter.platform, status=PostResult.STATUS_POSTED, external_url=url,
            ))
        except AdapterError as e:
            logger.exception('publish to %s failed', adapter.platform)
            results.append(PostResult.objects.create(
                draft=draft, platform=adapter.platform, status=PostResult.STATUS_FAILED, detail=str(e)[:255],
            ))
    return results


def _public_media_base():
    import os
    return os.environ.get('PUBLIC_MEDIA_BASE_URL', '')
