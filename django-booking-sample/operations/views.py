from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views import generic
from django.views.decorators.http import require_POST

from attendance.models import Shift
from booking.models import Staff, Store
from .models import BusinessDay, ChecklistTask
from . import services


def user_belongs_to_store(user, store):
    return user.is_superuser or Staff.objects.filter(user=user, store=store).exists()


class StoreStaffOnlyMixin(LoginRequiredMixin, UserPassesTestMixin):
    """その店舗のスタッフ(またはスーパーユーザー)のみ許可。"""
    raise_exception = True

    def test_func(self):
        store = get_object_or_404(Store, pk=self.kwargs['store_pk'])
        return user_belongs_to_store(self.request.user, store)


class TodayDashboard(StoreStaffOnlyMixin, generic.TemplateView):
    """当日の開店ダッシュボード(チェックリスト・シフト・開店ボタン)。"""
    template_name = 'operations/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        store = get_object_or_404(Store, pk=self.kwargs['store_pk'])
        today = timezone.localdate()
        business_day = services.start_business_day(store, today)
        context['store'] = store
        context['business_day'] = business_day
        context['tasks'] = business_day.tasks.all()
        context['shifts'] = Shift.objects.on_duty(store, today)
        return context


@require_POST
@login_required
def toggle_task(request, task_pk):
    task = get_object_or_404(ChecklistTask.objects.select_related('business_day__store'), pk=task_pk)
    if not user_belongs_to_store(request.user, task.business_day.store):
        raise PermissionDenied
    if task.is_done:
        task.is_done = False
        task.done_at = None
        task.done_by = None
        task.save(update_fields=['is_done', 'done_at', 'done_by'])
    else:
        task.mark_done(request.user)
    return redirect('operations:dashboard', store_pk=task.business_day.store.pk)


@require_POST
@login_required
def open_store(request, store_pk):
    store = get_object_or_404(Store, pk=store_pk)
    if not user_belongs_to_store(request.user, store):
        raise PermissionDenied
    business_day = services.start_business_day(store, timezone.localdate())
    services.open_store(business_day, request.user)
    messages.success(request, f'{store.name} を開店しました。自動処理の結果はチェックリストを確認してください。')
    return redirect('operations:dashboard', store_pk=store.pk)


@require_POST
@login_required
def close_store(request, store_pk):
    store = get_object_or_404(Store, pk=store_pk)
    if not user_belongs_to_store(request.user, store):
        raise PermissionDenied
    business_day = services.start_business_day(store, timezone.localdate())
    services.close_store(business_day)
    messages.success(request, f'{store.name} を閉店しました。')
    return redirect('operations:dashboard', store_pk=store.pk)
