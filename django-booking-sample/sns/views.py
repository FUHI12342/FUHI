from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views import generic
from django.views.decorators.http import require_POST

from booking.models import Store
from booking.access import user_belongs_to_store
from .models import PostDraft
from . import services


class DraftList(LoginRequiredMixin, UserPassesTestMixin, generic.ListView):
    template_name = 'sns/draft_list.html'
    raise_exception = True
    paginate_by = 20

    def test_func(self):
        store = get_object_or_404(Store, pk=self.kwargs['store_pk'])
        if not store.enable_sns:
            raise Http404('この店舗ではSNS投稿機能が無効です。')
        return user_belongs_to_store(self.request.user, store)

    def get_queryset(self):
        self.store = get_object_or_404(Store, pk=self.kwargs['store_pk'])
        return PostDraft.objects.filter(store=self.store).prefetch_related('results')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['store'] = self.store
        return context


class DraftDetail(LoginRequiredMixin, UserPassesTestMixin, generic.DetailView):
    model = PostDraft
    template_name = 'sns/draft_detail.html'
    raise_exception = True

    def test_func(self):
        draft = get_object_or_404(PostDraft, pk=self.kwargs['pk'])
        if not draft.store.enable_sns:
            raise Http404('この店舗ではSNS投稿機能が無効です。')
        return user_belongs_to_store(self.request.user, draft.store)


@require_POST
@login_required
def regenerate(request, store_pk):
    store = get_object_or_404(Store, pk=store_pk)
    if not store.enable_sns:
        raise Http404('この店舗ではSNS投稿機能が無効です。')
    if not user_belongs_to_store(request.user, store):
        raise PermissionDenied
    draft = services.generate_draft(store, timezone.localdate())
    messages.success(request, '下書きを再生成しました。内容を確認して承認してください。')
    return redirect('sns:draft_detail', pk=draft.pk)


@require_POST
@login_required
def approve(request, pk):
    draft = get_object_or_404(PostDraft, pk=pk)
    if not draft.store.enable_sns:
        raise Http404('この店舗ではSNS投稿機能が無効です。')
    if not user_belongs_to_store(request.user, draft.store, require_manager=True):
        raise PermissionDenied
    if draft.status == PostDraft.STATUS_APPROVED:
        # 承認済み: 失敗・未記録のプラットフォームだけ再配信(投稿済み・手動はスキップ)
        results = services.retry_unfinished(draft)
        if results:
            messages.success(request, f'{len(results)}件のプラットフォームへ再配信を試みました。結果を確認してください。')
        else:
            messages.info(request, '再配信が必要なプラットフォームはありません(投稿済み、または手動投稿の対象です)。')
    else:
        services.publish_draft(draft, request.user)
        messages.success(request, '承認しました。各プラットフォームの結果を確認してください。')
    return redirect('sns:draft_detail', pk=draft.pk)
