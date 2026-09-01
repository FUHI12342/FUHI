import csv
import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views import generic
from django.views.decorators.http import require_POST

from booking.models import Staff, Store
from .models import Shift, TimeRecord


class MyAttendance(LoginRequiredMixin, generic.TemplateView):
    """自分の当日シフトと打刻状況。"""
    template_name = 'attendance/my_attendance.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        staff_list = Staff.objects.filter(user=self.request.user, is_on_roster=True).select_related('store')
        rows = []
        for staff in staff_list:
            shift = Shift.objects.filter(staff=staff, date=today).exclude(status=Shift.STATUS_ABSENT).first()
            record = TimeRecord.objects.filter(staff=staff, date=today).first()
            rows.append({'staff': staff, 'shift': shift, 'record': record})
        context['rows'] = rows
        context['today'] = today
        return context


@require_POST
@login_required
def clock_in(request, staff_pk):
    staff = get_object_or_404(Staff, pk=staff_pk)
    if staff.user != request.user and not request.user.is_superuser:
        raise PermissionDenied
    today = timezone.localdate()
    record, _created = TimeRecord.objects.get_or_create(staff=staff, date=today)
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
    staff = get_object_or_404(Staff, pk=staff_pk)
    if staff.user != request.user and not request.user.is_superuser:
        raise PermissionDenied
    today = timezone.localdate()
    record = TimeRecord.objects.filter(staff=staff, date=today).first()
    if record is None or record.clock_in is None:
        messages.error(request, '出勤打刻がありません。')
    elif record.clock_out:
        messages.error(request, '本日はすでに退勤打刻済みです。')
    else:
        record.clock_out = timezone.now()
        record.save(update_fields=['clock_out'])
        messages.success(request, f'{staff.name} 退勤を打刻しました。')
    return redirect('attendance:my_attendance')


class MonthlyCsvExport(LoginRequiredMixin, UserPassesTestMixin, generic.View):
    """月次勤務実績CSV(給与計算SaaSへのインポート用)。管理者のみ。"""
    raise_exception = True

    def test_func(self):
        return self.request.user.is_superuser

    def get(self, request, store_pk, year, month):
        store = get_object_or_404(Store, pk=store_pk)
        first = datetime.date(year, month, 1)
        next_month = (first.replace(day=28) + datetime.timedelta(days=7)).replace(day=1)

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
            for s in Shift.objects.filter(
                staff__store=store, date__gte=first, date__lt=next_month
            ).exclude(status=Shift.STATUS_ABSENT)
        }
        tz = timezone.get_current_timezone()
        for record in records:
            shift = shifts_by_key.get((record.staff_id, record.date))
            writer.writerow([
                record.staff.name,
                record.date.isoformat(),
                shift.start_time.strftime('%H:%M') if shift else '',
                shift.end_time.strftime('%H:%M') if shift else '',
                record.clock_in.astimezone(tz).strftime('%H:%M') if record.clock_in else '',
                record.clock_out.astimezone(tz).strftime('%H:%M') if record.clock_out else '',
                record.worked_minutes if record.worked_minutes is not None else '',
            ])
        return response
