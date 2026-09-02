from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views import generic
from django.views.decorators.http import require_POST

from attendance.models import Shift
from booking.access import StoreAccessMixin, check_store_access
from booking.models import Store
from .models import ChecklistTask
from . import services


class TodayDashboard(StoreAccessMixin, generic.TemplateView):
    """当日の開店ダッシュボード(チェックリスト・シフト・開閉店ボタン)。"""
    template_name = 'operations/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        business_day = services.start_business_day(self.store, today)
        context.update(
            store=self.store,
            business_day=business_day,
            tasks=business_day.tasks.all(),
            shifts=Shift.objects.on_duty(self.store, today),
        )
        return context


@require_POST
@login_required
def toggle_task(request, task_pk):
    task = get_object_or_404(ChecklistTask.objects.select_related('business_day__store'), pk=task_pk)
    check_store_access(request.user, task.business_day.store)
    if task.is_done:
        task.mark_undone()
    else:
        task.mark_done(request.user)
    return redirect('operations:dashboard', store_pk=task.business_day.store.pk)


def _store_transition(request, store_pk, action, done_message):
    """開店・閉店の共通処理。店長のみ。"""
    store = get_object_or_404(Store, pk=store_pk)
    check_store_access(request.user, store, manager=True)
    business_day = services.start_business_day(store, timezone.localdate())
    action(business_day, request.user)
    messages.success(request, done_message.format(store=store.name))
    return redirect('operations:dashboard', store_pk=store.pk)


@require_POST
@login_required
def open_store(request, store_pk):
    return _store_transition(
        request, store_pk, services.open_store,
        '{store} を開店しました。自動処理の結果はチェックリストを確認してください。',
    )


@require_POST
@login_required
def close_store(request, store_pk):
    return _store_transition(
        request, store_pk, lambda business_day, user: services.close_store(business_day),
        '{store} を閉店しました。',
    )
