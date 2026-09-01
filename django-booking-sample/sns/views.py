from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views import generic
from django.views.decorators.http import require_POST

from booking.access import StoreAccessMixin, check_store_access
from booking.models import Store
from .models import PostDraft
from . import services

FEATURE = 'enable_sns'


class DraftList(StoreAccessMixin, generic.ListView):
    template_name = 'sns/draft_list.html'
    feature_flag = FEATURE
    paginate_by = 20

    def get_queryset(self):
        return PostDraft.objects.filter(store=self.store).prefetch_related('results')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['store'] = self.store
        return context


class DraftDetail(StoreAccessMixin, generic.DetailView):
    model = PostDraft
    template_name = 'sns/draft_detail.html'
    feature_flag = FEATURE

    def get_store(self):
        return get_object_or_404(PostDraft.objects.select_related('store'), pk=self.kwargs['pk']).store


@require_POST
@login_required
def regenerate(request, store_pk):
    store = get_object_or_404(Store, pk=store_pk)
    check_store_access(request.user, store, feature=FEATURE)
    draft = services.generate_draft(store, timezone.localdate())
    messages.success(request, '下書きを再生成しました。内容を確認して承認してください。')
    return redirect('sns:draft_detail', pk=draft.pk)


@require_POST
@login_required
def approve(request, pk):
    """承認して配信(店長のみ)。承認済みなら未完了プラットフォームの再配信。"""
    draft = get_object_or_404(PostDraft.objects.select_related('store'), pk=pk)
    check_store_access(request.user, draft.store, feature=FEATURE, manager=True)
    if draft.status == PostDraft.STATUS_APPROVED:
        results = services.retry_unfinished(draft)
        if results:
            messages.success(request, f'{len(results)}件のプラットフォームへ再配信を試みました。結果を確認してください。')
        else:
            messages.info(request, '再配信が必要なプラットフォームはありません(投稿済み、または手動投稿の対象です)。')
    else:
        services.publish_draft(draft, request.user)
        messages.success(request, '承認しました。各プラットフォームの結果を確認してください。')
    return redirect('sns:draft_detail', pk=draft.pk)
