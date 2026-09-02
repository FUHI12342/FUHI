import csv
import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views import generic
from django.views.decorators.http import require_POST

from booking.access import StoreAccessMixin
from booking.models import Staff
from .models import Shift, TimeRecord


class MyAttendance(LoginRequiredMixin, generic.TemplateView):
    """自分の当日シフトと打刻状況。"""
    template_name = 'attendance/my_attendance.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        staff_list = Staff.objects.filter(user=self.request.user, is_on_roster=True).select_related('store')
        context['rows'] = [
            {
                'staff': staff,
                'shift': Shift.objects.filter(staff=staff, date=today).exclude(status=Shift.STATUS_ABSENT).first(),
                'record': TimeRecord.objects.filter(staff=staff, date=today).first(),
            }
            for staff in staff_list
        ]
        context['today'] = today
        return context


def _own_staff(request, staff_pk):
    """打刻対象のスタッフ。本人(またはスーパーユーザー)以外は 403。"""
    staff = get_object_or_404(Staff, pk=staff_pk)
    if staff.user != request.user and not request.user.is_superuser:
        raise PermissionDenied
    return staff


@require_POST
@login_required
def clock_in(request, staff_pk):
    staff = _own_staff(request, staff_pk)
    record, _created = TimeRecord.objects.get_or_create(staff=staff, date=timezone.localdate())
    if record.clock_in:
        messages.error(request, '本日はすでに出勤打刻済みです。')
    else:
        record.clock_in = timezone.now()
        record.save(update_fields=['clock_in'])
        messages.success(request, f'{staff.name} 出勤を打刻しました。')
    return redirect('attendance:my_attendance')


@require_POST
@login_required
def clock_out(request, staff_pk):
    staff = _own_staff(request, staff_pk)
    record = TimeRecord.objects.filter(staff=staff, date=timezone.localdate()).first()
    if record is None or record.clock_in is None:
        messages.error(request, '出勤打刻がありません。')
    elif record.clock_out:
        messages.error(request, '本日はすでに退勤打刻済みです。')
    else:
        record.clock_out = timezone.now()
        record.save(update_fields=['clock_out'])
        messages.success(request, f'{staff.name} 退勤を打刻しました。')
    return redirect('attendance:my_attendance')


def _month_range(year, month):
    first = datetime.date(year, month, 1)
    next_month = (first.replace(day=28) + datetime.timedelta(days=7)).replace(day=1)
    return first, next_month


class MonthlyCsvExport(StoreAccessMixin, generic.View):
    """月次勤務実績CSV(給与計算SaaSへのインポート用)。その店舗の店長のみ。"""
    require_manager = True

    def get(self, request, store_pk, year, month):
        store = self.store
        first, next_month = _month_range(year, month)

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="attendance_{store.pk}_{year}{month:02d}.csv"'
        writer = csv.writer(response)
        writer.writerow(['スタッフ', '日付', 'シフト開始', 'シフト終了', '出勤打刻', '退勤打刻', '実働(分)'])

        records = (
            TimeRecord.objects.filter(staff__store=store, date__gte=first, date__lt=next_month)
            .select_related('staff')
            .order_by('staff__name', 'date')
        )
        # 打刻1行ごとにシフトを引かない(当月分を一括ロードして突合する)
        shifts_by_key = {
            (s.staff_id, s.date): s
            for s in Shift.objects.filter(staff__store=store, date__gte=first, date__lt=next_month)
            .exclude(status=Shift.STATUS_ABSENT)
        }
        tz = timezone.get_current_timezone()
        fmt = lambda dt: dt.astimezone(tz).strftime('%H:%M') if dt else ''  # noqa: E731
        for record in records:
            shift = shifts_by_key.get((record.staff_id, record.date))
            writer.writerow([
                record.staff.name,
                record.date.isoformat(),
                shift.start_time.strftime('%H:%M') if shift else '',
                shift.end_time.strftime('%H:%M') if shift else '',
                fmt(record.clock_in),
                fmt(record.clock_out),
                record.worked_minutes if record.worked_minutes is not None else '',
            ])
        return response
