import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.http import urlencode
from django.views import generic
from django.views.decorators.http import require_POST

from . import reservations
from .access import StoreAccessMixin, check_store_access, require_web_reservation
from .forms import ReservationForm, ReservationSearchForm
from .models import Seat, Schedule, Staff, Store, WalkIn
from .timeslots import business_day_span, make_aware_datetime

User = get_user_model()


# ---------------------------------------------------------------------------
# 権限ミックスイン(既存の予約サイト部分)
# ---------------------------------------------------------------------------

class OnlyStaffMixin(UserPassesTestMixin):
    raise_exception = True

    def test_func(self):
        staff = get_object_or_404(Staff, pk=self.kwargs['pk'])
        return staff.user == self.request.user or self.request.user.is_superuser


class OnlyScheduleMixin(UserPassesTestMixin):
    raise_exception = True

    def test_func(self):
        schedule = get_object_or_404(Schedule, pk=self.kwargs['pk'])
        if self.request.user.is_superuser:
            return True
        # 座席予約(staff 無し)はマイページの対象外
        return schedule.staff is not None and schedule.staff.user == self.request.user


class OnlyUserMixin(UserPassesTestMixin):
    raise_exception = True

    def test_func(self):
        return self.kwargs['pk'] == self.request.user.pk or self.request.user.is_superuser


# ---------------------------------------------------------------------------
# 公開ページ(店舗一覧・スタッフ一覧・予約カレンダー)
# ---------------------------------------------------------------------------

class StoreList(generic.ListView):
    model = Store
    ordering = 'name'


class StaffList(generic.ListView):
    model = Staff
    ordering = 'name'

    def get_queryset(self):
        self.store = get_object_or_404(Store, pk=self.kwargs['pk'])
        return super().get_queryset().filter(store=self.store)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['store'] = self.store
        return context


def _schedules_between(staff, start_time, end_time):
    """期間に重なる予約。深夜枠は timeslots 側で前営業日に割り当てる。"""
    return Schedule.objects.filter(staff=staff).exclude(Q(start__gt=end_time) | Q(end__lt=start_time))


class StaffCalendar(generic.TemplateView):
    """スタッフの週間カレンダー。営業時間×7日のグリッドで空き(True)/予約済み(False)を示す。"""
    template_name = 'booking/calendar.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        staff = get_object_or_404(Staff, pk=self.kwargs['pk'])
        store = staff.store
        today = datetime.date.today()

        year, month, day = (self.kwargs.get(k) for k in ('year', 'month', 'day'))
        base_date = datetime.date(year, month, day) if year and month and day else today
        days = [base_date + datetime.timedelta(days=i) for i in range(7)]

        hours = store.business_hours
        calendar = {hour: {d: True for d in days} for hour in hours}

        start_time = make_aware_datetime(days[0].year, days[0].month, days[0].day, hours[0])
        end_time = make_aware_datetime(days[-1].year, days[-1].month, days[-1].day, hours[-1])
        for schedule in _schedules_between(staff, start_time, end_time):
            booking_date, booking_hour = store.business_slot(timezone.localtime(schedule.start))
            if booking_hour in calendar and booking_date in calendar[booking_hour]:
                calendar[booking_hour][booking_date] = False

        context.update(
            staff=staff, calendar=calendar, days=days,
            start_day=days[0], end_day=days[-1],
            before=days[0] - datetime.timedelta(days=7), next=days[-1] + datetime.timedelta(days=1),
            today=today, public_holidays=settings.PUBLIC_HOLIDAYS,
        )
        return context


class Booking(generic.CreateView):
    """予約フォーム。二重予約の最終判定は DB の UNIQUE 制約に委ねる。"""
    model = Schedule
    fields = ('name',)
    template_name = 'booking/booking.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['staff'] = get_object_or_404(Staff, pk=self.kwargs['pk'])
        return context

    def form_valid(self, form):
        staff = get_object_or_404(Staff, pk=self.kwargs['pk'])
        year, month, day, hour = (self.kwargs.get(k) for k in ('year', 'month', 'day', 'hour'))
        schedule = form.save(commit=False)
        schedule.staff = staff
        schedule.start = make_aware_datetime(year, month, day, hour)
        schedule.end = schedule.start + datetime.timedelta(hours=1)
        try:
            with transaction.atomic():
                schedule.save()
        except IntegrityError:
            messages.error(self.request, 'すみません、入れ違いで予約がありました。別の日時はどうですか。')
        return redirect('booking:calendar', pk=staff.pk, year=year, month=month, day=day)


# ---------------------------------------------------------------------------
# マイページ(スタッフ自身の予約管理)
# ---------------------------------------------------------------------------

class MyPage(LoginRequiredMixin, generic.TemplateView):
    template_name = 'booking/my_page.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['staff_list'] = Staff.objects.filter(user=self.request.user).order_by('name')
        context['schedule_list'] = Schedule.objects.filter(
            staff__user=self.request.user, start__gte=timezone.now()
        ).order_by('name')
        return context


class MyPageWithPk(OnlyUserMixin, generic.TemplateView):
    template_name = 'booking/my_page.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pk = self.kwargs['pk']
        context['user'] = get_object_or_404(User, pk=pk)
        context['staff_list'] = Staff.objects.filter(user__pk=pk).order_by('name')
        context['schedule_list'] = Schedule.objects.filter(
            staff__user__pk=pk, start__gte=timezone.now()
        ).order_by('name')
        return context


class MyPageCalendar(OnlyStaffMixin, StaffCalendar):
    template_name = 'booking/my_page_calendar.html'


class MyPageDayDetail(OnlyStaffMixin, generic.TemplateView):
    """1営業日の予約一覧(時間帯ごと)。"""
    template_name = 'booking/my_page_day_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        staff = get_object_or_404(Staff, pk=self.kwargs['pk'])
        store = staff.store
        date = datetime.date(self.kwargs['year'], self.kwargs['month'], self.kwargs['day'])

        hours = store.business_hours
        calendar = {hour: [] for hour in hours}
        start_time = make_aware_datetime(date.year, date.month, date.day, hours[0])
        end_time = make_aware_datetime(date.year, date.month, date.day, hours[-1])
        for schedule in _schedules_between(staff, start_time, end_time):
            booking_date, booking_hour = store.business_slot(timezone.localtime(schedule.start))
            if booking_hour in calendar and booking_date == date:
                calendar[booking_hour].append(schedule)

        context['calendar'] = calendar
        context['staff'] = staff
        return context


class MyPageSchedule(OnlyScheduleMixin, generic.UpdateView):
    model = Schedule
    fields = ('start', 'end', 'name')
    success_url = reverse_lazy('booking:my_page')


class MyPageScheduleDelete(OnlyScheduleMixin, generic.DeleteView):
    model = Schedule
    success_url = reverse_lazy('booking:my_page')


@require_POST
def my_page_holiday_add(request, pk, year, month, day, hour):
    staff = get_object_or_404(Staff, pk=pk)
    if staff.user != request.user and not request.user.is_superuser:
        raise PermissionDenied
    start = make_aware_datetime(year, month, day, hour)
    try:
        with transaction.atomic():
            Schedule.objects.create(
                staff=staff, start=start, end=start + datetime.timedelta(hours=1),
                name='休暇(システムによる追加)',
            )
    except IntegrityError:
        messages.error(request, 'この時間には既に予約があります。')
    return redirect('booking:my_page_day_detail', pk=pk, year=year, month=month, day=day)


# ---------------------------------------------------------------------------
# 座席ボード・ウォークイン(機能フラグ: enable_seat_board)
# ---------------------------------------------------------------------------

class SeatBoard(StoreAccessMixin, generic.TemplateView):
    """当日の座席ボード。時間帯×座席のグリッドで予約とウォークインを可視化する。"""
    template_name = 'booking/seat_board.html'
    feature_flag = 'enable_seat_board'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        store = self.store
        date = timezone.localdate()
        seats = list(store.seats.filter(is_active=True))

        day_start, day_end = business_day_span(store, date)
        schedules = Schedule.objects.filter(
            seat__store=store, start__gte=day_start, start__lt=day_end
        ).select_related('seat')
        by_seat_hour = {}
        for schedule in schedules:
            slot_date, slot_hour = store.business_slot(timezone.localtime(schedule.start))
            if slot_date == date:
                by_seat_hour[(schedule.seat_id, slot_hour)] = schedule

        context.update(
            store=store, date=date, seats=seats,
            rows=[
                {'hour': hour, 'cells': [
                    {'seat': seat, 'schedule': by_seat_hour.get((seat.pk, hour))} for seat in seats
                ]}
                for hour in store.business_hours
            ],
            active_walkins=WalkIn.objects.filter(seat__store=store, left_at__isnull=True).select_related('seat'),
        )
        return context


@require_POST
def walkin_start(request, seat_pk):
    seat = get_object_or_404(Seat.objects.select_related('store'), pk=seat_pk)
    check_store_access(request.user, seat.store, feature='enable_seat_board')
    try:
        party_size = max(1, int(request.POST.get('party_size', '1')))
    except ValueError:
        party_size = 1
    try:
        # 同時タップの競合は DB の部分UNIQUE制約(unique_active_walkin_per_seat)で防ぐ
        with transaction.atomic():
            WalkIn.objects.create(seat=seat, party_size=party_size)
        messages.success(request, f'{seat.name} に{party_size}名 着席。')
    except IntegrityError:
        messages.error(request, f'{seat.name} は使用中です。')
    return redirect('booking:seat_board', pk=seat.store.pk)


@require_POST
def walkin_end(request, pk):
    walkin = get_object_or_404(WalkIn.objects.select_related('seat__store'), pk=pk)
    check_store_access(request.user, walkin.seat.store, feature='enable_seat_board')
    if walkin.left_at is None:
        walkin.left_at = timezone.now()
        walkin.save(update_fields=['left_at'])
        messages.success(request, f'{walkin.seat.name} 離席。')
    return redirect('booking:seat_board', pk=walkin.seat.store.pk)


# ---------------------------------------------------------------------------
# 顧客向けWeb座席予約(飲食業態・ログイン不要。機能フラグ: enable_web_reservation)
# ---------------------------------------------------------------------------

class WebReservationMixin:
    """URL の store pk から店舗を引き、Web座席予約を受け付ける店舗でなければ 404。"""

    def dispatch(self, request, *args, **kwargs):
        self.store = get_object_or_404(Store, pk=kwargs['pk'])
        require_web_reservation(self.store)
        return super().dispatch(request, *args, **kwargs)


class WebReservation(WebReservationMixin, generic.TemplateView):
    """人数・日付を入れると、時間帯ごとの空き座席候補を出す。"""
    template_name = 'booking/web_reservation.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.GET:
            form = ReservationSearchForm(self.request.GET)
        else:
            form = ReservationSearchForm(initial={'date': timezone.localdate()})
        context.update(store=self.store, form=form, slots=None)
        if self.request.GET and form.is_valid():
            date, party_size = form.cleaned_data['date'], form.cleaned_data['party_size']
            context.update(
                date=date, party_size=party_size,
                slots=reservations.available_slots(self.store, date, party_size),
            )
        return context


class WebReservationConfirm(WebReservationMixin, generic.FormView):
    """選んだ枠・座席で連絡先を入力して確定する。"""
    template_name = 'booking/web_reservation_confirm.html'
    form_class = ReservationForm

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.date = datetime.date(kwargs['year'], kwargs['month'], kwargs['day'])
        self.hour = kwargs['hour']
        try:
            self.party_size = max(1, int(request.GET.get('party_size', request.POST.get('party_size', '1'))))
        except ValueError:
            self.party_size = 1

    def dispatch(self, request, *args, **kwargs):
        self.seat = get_object_or_404(Seat.objects.select_related('store'), pk=kwargs['seat_pk'], store_id=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            store=self.store, seat=self.seat, date=self.date, hour=self.hour,
            slot_label=reservations.slot_label(self.hour), party_size=self.party_size,
        )
        return context

    def form_valid(self, form):
        data = form.cleaned_data
        try:
            schedule = reservations.create_reservation(
                store=self.store, seat=self.seat, date=self.date, hour=self.hour,
                party_size=self.party_size, name=data['name'],
                email=data['customer_email'], phone=data['customer_phone'],
            )
        except reservations.SlotUnavailable as exc:
            messages.error(self.request, str(exc))
            return redirect(self._search_url())
        detail_url = self.request.build_absolute_uri(
            reverse('booking:web_reservation_detail', kwargs={'token': schedule.cancel_token})
        )
        if reservations.send_confirmation_email(schedule, detail_url):
            messages.success(self.request, f'{schedule.customer_email} に確認メールを送りました。')
        else:
            messages.warning(self.request, '確認メールを送れませんでした。この画面のURLを控えてください。')
        return redirect('booking:web_reservation_detail', token=schedule.cancel_token)

    def _search_url(self):
        query = urlencode({'date': self.date.isoformat(), 'party_size': self.party_size})
        return f"{reverse('booking:web_reservation', kwargs={'pk': self.store.pk})}?{query}"


def _web_reservations():
    """トークンで参照できる座席予約。座席が削除された予約(seat=NULL)は存在しない扱い。"""
    return Schedule.objects.filter(seat__isnull=False).select_related('seat__store')


class WebReservationDetail(generic.DetailView):
    """予約確認・キャンセル画面。ログイン不要で、URL のトークンだけが認証。"""
    template_name = 'booking/web_reservation_detail.html'
    context_object_name = 'schedule'

    def get_object(self, queryset=None):
        return get_object_or_404(_web_reservations(), cancel_token=self.kwargs['token'])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['store'] = self.object.seat.store
        return context


@require_POST
def web_reservation_cancel(request, token):
    schedule = get_object_or_404(_web_reservations(), cancel_token=token)
    store = schedule.seat.store
    if reservations.cancel_reservation(schedule):
        messages.success(request, 'ご予約をキャンセルしました。またのご利用をお待ちしています。')
        return redirect('booking:web_reservation', pk=store.pk)
    messages.error(request, '開始時刻を過ぎた予約はこの画面から取り消せません。店舗へ直接ご連絡ください。')
    return redirect('booking:web_reservation_detail', token=token)
