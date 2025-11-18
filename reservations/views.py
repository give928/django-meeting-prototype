import logging
from datetime import datetime, timedelta
from typing import Dict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import Group
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Subquery, OuterRef, Exists
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views import View

from accounts.caches import DepartmentCache
from common.decorators import json_login_required
from common.utils import RequestUtils
from reservations.forms import ReservationForm
from reservations.models import Reservation, Attendee
from rooms.models import Room

logger = logging.getLogger(__name__)
size = 10


@login_required(login_url='sign-in')
def reservations(request):
    page = RequestUtils.get_page(request)
    date = request.GET.get('date')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    user = request.GET.get('user')
    attendee = request.GET.get('attendee')

    date, start_datetime, end_datetime = initialize_reservations_parameters(date, start_date, end_date)

    q = Q(is_active=True)
    q &= Q(start_datetime__gte=start_datetime)
    q &= Q(start_datetime__lt=end_datetime)
    if user:
        q &= Q(created_user__username__icontains=user)
    if attendee:
        q &= Exists(
            Reservation.attendees.through.objects.filter(
                reservation_id=OuterRef('id'),
                user__username__icontains=attendee
            )
        )

    active_reservations = \
        (Reservation.objects
         .select_related('room', 'created_user')
         .prefetch_related('attendees')
         .only(
            'id',
            'title',
            'description',
            'start_datetime',
            'end_datetime',
            'created_user_id',
            'created_user__username',
            'room_id',
            'room__name',
            'room__seat_count',
            'room__capacity_count',
            'room__has_monitor',
            'room__has_microphone'
        )
         .annotate(
            group_name=Subquery(
                Group.objects.filter(user__id=OuterRef('created_user_id'))
                .order_by('id')
                .values('name')[:1]
            ),
        )
         .filter(q)
         .order_by('-start_datetime', 'room_id'))

    paginator = Paginator(active_reservations, size)
    page_reservations = paginator.get_page(page)

    for r in page_reservations:
        r.attendees_names = ', '.join([a.username for a in r.attendees.all()])
        r.attendees_count = r.attendees.all().count()
        r.readonly = not r.can_edit(request.user)

    rooms = Room.objects.filter(is_active=True).all()

    return render(request, 'reservations/reservations.html', {
        'page_reservations': page_reservations,
        'rooms': rooms,
        'start_date': start_datetime.strftime('%Y-%m-%d'),
        'end_date': (end_datetime - timedelta(days=1)).strftime('%Y-%m-%d'),
        'date': date.strftime('%Y-%m-%d'),
    })


def initialize_reservations_parameters(date: str | None, start_date: str | None, end_date: str | None) -> tuple[datetime, datetime, datetime]:
    now = timezone.localtime()

    start_of_week = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    if date:
        date_obj = datetime.strptime(date, '%Y-%m-%d').date()
    else:
        date_obj = now.date()

    if start_date:
        start_datetime = timezone.make_aware(
            datetime.strptime(start_date, '%Y-%m-%d')
        )
    else:
        start_datetime = start_of_week

    if end_date:
        end_datetime = timezone.make_aware(
            datetime.strptime(end_date, '%Y-%m-%d')
        ) + timedelta(days=1)
    else:
        end_datetime = now.replace(
            hour=23, minute=59, second=59, microsecond=999999
        ) + timedelta(microseconds=1)

    return date_obj, start_datetime, end_datetime


class ReservationView(LoginRequiredMixin, View):
    reservation_form_class = ReservationForm
    template_name = 'reservations/reservation.html'

    def get(self, request, *args, **kwargs):
        pk = kwargs['pk']
        if pk == 0:
            return render(request, self.template_name, {'form': self.reservation_form_class(readonly=False), 'departments': DepartmentCache.find(is_active=True)})

        reservation = get_object_or_404(Reservation, pk=pk)
        attendees = [attendee.user.pk for attendee in Attendee.objects.select_related('user').filter(reservation=reservation).all()]

        return render(
            request,
            self.template_name,
            {
                'form': self.reservation_form_class(instance=reservation, readonly=not reservation.can_edit(request.user)),
                'attendees': attendees,
                'departments': DepartmentCache.find(is_active=True),
            })

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        form = self.reservation_form_class(request.POST)
        attendees = set(request.POST.getlist('attendees'))
        if form.is_valid():
            reservation = form.save(commit=False)
            reservation.created_user_id = request.user.pk
            reservation.last_modified_user_id = request.user.pk
            reservation.save()
            reservation.save_attendees(attendees, request.user)
            messages.success(request, '예약이 등록되었습니다.')
            return redirect('reservations')

        return self.error(attendees, form, request)

    @transaction.atomic
    def put(self, request, *args, **kwargs):
        pk = kwargs['pk']
        reservation = get_object_or_404(Reservation.objects.prefetch_related('attendees'), pk=pk)
        if not reservation.can_edit(request.user):
            messages.error(request, '수정 권한이 없습니다.\n(리더, 작성자, 참석자만 수정할 수 있습니다.)')
            return redirect('reservations')
        form = self.reservation_form_class(request.POST, instance=reservation)
        attendees = set(map(int, request.POST.getlist('attendees')))
        if form.is_valid():
            reservation = form.save(commit=False)
            reservation.last_modified_user_id = request.user.pk
            reservation.last_modified_date = timezone.now()
            update_fields = ['room_id', 'title', 'description', 'start_datetime', 'end_datetime', 'last_modified_user_id', 'last_modified_date']
            reservation.save(update_fields=update_fields)
            reservation.save_attendees(attendees, request.user)
            messages.success(request, '예약이 수정되었습니다.')
            return redirect('reservations')

        return self.error(attendees, form, request)

    def delete(self, request, *args, **kwargs):
        reservation = get_object_or_404(Reservation, pk=kwargs['pk'])
        reservation.is_active = False
        reservation.last_modified_user_id = request.user.pk
        reservation.last_modified_date = timezone.now()
        update_fields = ['is_active', 'last_modified_user_id', 'last_modified_date']
        reservation.save(update_fields=update_fields)
        messages.success(request, '예약이 삭제되었습니다.')
        return redirect('reservations')

    def error(self, attendees, form: ReservationForm, request) -> HttpResponse:
        errors = []
        for field, field_errors in form.errors.items():
            errors.extend(field_errors)
        if errors:
            combined_message = '\n'.join(set(errors))
            messages.warning(request, combined_message)
        return render(request, self.template_name, {'form': form, 'attendees': [int(u) for u in attendees], 'departments': DepartmentCache.find(is_active=True)})


reservation_margin_hours = 4
reservation_default_start_hour = 8
reservation_default_end_hour = 22


@json_login_required
def reservations_schedules(request, room_id):
    try:
        readonly = request.GET.get('readonly')
        start_datetime = request.GET.get('start')
        end_datetime = request.GET.get('end')
        reservation_id = request.GET.get('reservation_id')
        recommend, start_datetime, start_of_day, end_datetime, end_of_day = initialize_period(readonly, start_datetime, end_datetime)

        q = Q(room_id=room_id,
              end_datetime__gte=start_of_day,
              start_datetime__lte=end_of_day,
              is_active=True)
        if readonly != 'true' and reservation_id:
            q &= ~Q(pk=reservation_id)

        saved_reservations = list(
            Reservation.objects
            .select_related('created_user')
            .only('id', 'title', 'start_datetime', 'end_datetime', 'created_user', 'created_user__username')
            .annotate(
                group_name=Subquery(
                    Group.objects.filter(user__id=OuterRef('created_user_id'))
                    .order_by('id')
                    .values('name')[:1]
                )
            )
            .filter(q)
            .order_by('start_datetime')
        )

        if saved_reservations:
            last_end_datetime = saved_reservations[-1].end_datetime

            if last_end_datetime >= end_of_day:
                end_of_day = last_end_datetime + timedelta(hours=reservation_margin_hours)

        timelines = []
        status = 'success'
        message = ''
        last_end = start_of_day

        for r in saved_reservations:
            r_start_datetime = r.start_datetime
            r_end_datetime = r.end_datetime

            if not recommend and r_start_datetime < end_datetime and r_end_datetime > start_datetime:
                # raise ValidationError(f'이 시간에는 이미 다른 예약이 있습니다.\n({r_start_datetime.astimezone().strftime('%Y-%m-%d %H:%M')} ~ {r_end_datetime.astimezone().strftime('%Y-%m-%d %H:%M')})\n다른 시간으로 선택해주세요.')
                status = 'error'
                message = (f'{start_datetime.astimezone().strftime('%Y-%m-%d %H:%M')} ~ {end_datetime.astimezone().strftime('%Y-%m-%d %H:%M')}\n시간에 이미 다른 예약이 있습니다.'
                           f'\n\n회의: {r.title}\n시간: {r_start_datetime.astimezone().strftime('%Y-%m-%d %H:%M')} ~ {r_end_datetime.astimezone().strftime('%Y-%m-%d %H:%M')}'
                           f'\n예약자: [{r.group_name}]{r.created_user.username}'
                           f'\n\n다른 시간으로 선택해주세요.')

            if r_start_datetime > last_end:
                start_offset = (last_end - start_of_day).total_seconds() / 60
                end_offset = (r_start_datetime - start_of_day).total_seconds() / 60
                timelines.append({
                    'status': 'available',
                    'title': '예약 가능',
                    'start_offset': start_offset,
                    'end_offset': end_offset,
                })

            start_offset = (r_start_datetime - start_of_day).total_seconds() / 60
            end_offset = (r_end_datetime - start_of_day).total_seconds() / 60
            timelines.append({
                'status': 'reserved' if str(r.id) != reservation_id else 'selected',
                'id': r.id,
                'time': f'{r.start_datetime.astimezone().strftime('%H:%M')} ~ {r.end_datetime.astimezone().strftime('%H:%M')}',
                'title': f'{r.title}' if str(r.id) != reservation_id else '현재 예약',
                'user': f'[{r.group_name}]{r.created_user.username}',
                'start_offset': start_offset,
                'end_offset': end_offset,
                'readonly': not r.can_edit(request.user)
            })

            last_end = max(last_end, r_end_datetime)

        if last_end < end_of_day:
            start_offset = (last_end - start_of_day).total_seconds() / 60
            end_offset = (end_of_day - start_of_day).total_seconds() / 60
            timelines.append({
                'status': 'available',
                'title': '예약 가능',
                'start_offset': start_offset,
                'end_offset': end_offset,
            })
        else:
            end_of_day = last_end

        if recommend:
            min_offset = int((start_datetime - start_of_day).total_seconds() / 60)
            end_offset = -1
            insert_selected_timeline(timelines, min_offset, -1, end_offset)
        elif readonly != 'true' and status == 'success':
            start_offset = int((start_datetime - start_of_day).total_seconds() / 60)
            end_offset = int((end_datetime - start_of_day).total_seconds() / 60)
            insert_selected_timeline(timelines, start_offset, start_offset, end_offset)

        return JsonResponse({'status': status, 'message': message, 'start': start_of_day.astimezone(), 'end': end_of_day.astimezone(), 'timelines': timelines})
    except Exception as e:
        logging.error('Error:', e)
        return JsonResponse({'status': 'error', 'message': '데이터 처리 중 예외가 발생했습니다.'})


def initialize_period(readonly: str | None, start_datetime: str | None, end_datetime: str | None) -> tuple[bool, datetime, datetime, datetime, datetime]:
    recommend = False
    if start_datetime is None or start_datetime == '' or end_datetime is None or end_datetime == '':
        if readonly != 'true':
            recommend = True
        localtime = timezone.localtime() + timedelta(hours=1)
        start_datetime = localtime.replace(minute=0, second=0, microsecond=0)
        end_datetime = localtime.replace(minute=0, second=0, microsecond=0)
    else:
        start_datetime = timezone.make_aware(datetime.strptime(start_datetime, '%Y-%m-%dT%H:%M'), timezone.get_current_timezone())
        end_datetime = timezone.make_aware(datetime.strptime(end_datetime, '%Y-%m-%dT%H:%M'), timezone.get_current_timezone())

    if start_datetime.hour <= reservation_default_start_hour:
        start_of_day = (start_datetime - timedelta(hours=reservation_margin_hours)).replace(minute=0, second=0, microsecond=0)
    else:
        start_of_day = start_datetime.replace(hour=reservation_default_start_hour, minute=0, second=0, microsecond=0)
    if start_datetime.day != end_datetime.day or end_datetime.hour >= reservation_default_end_hour - reservation_margin_hours:
        end_of_day = (end_datetime + timedelta(hours=reservation_margin_hours)).replace(minute=0, second=0, microsecond=0)
    else:
        end_of_day = end_datetime.replace(hour=reservation_default_end_hour, minute=0, second=0, microsecond=0)
    return recommend, start_datetime, start_of_day, end_datetime, end_of_day


def insert_selected_timeline(timelines: list[Dict], min_offset: int, start_offset: int, end_offset: int):
    for i, timeline in enumerate(timelines):
        if timeline.get('status', 'reserved') != 'available':
            continue
        if min_offset >= timeline.get('end_offset', 0.0):
            continue
        if start_offset != -1 and start_offset < timeline.get('start_offset', 0.0):
            continue

        if start_offset == -1:
            start_offset = max(timeline.get('start_offset', 0), min_offset)
        index = i
        if start_offset > timeline.get('start_offset', 0):
            timelines.insert(index, {
                'status': 'available',
                'title': '예약 가능',
                'start_offset': timeline.get('start_offset', 0),
                'end_offset': start_offset,
            })
            index += 1
        if end_offset == -1:
            end_offset = start_offset + 60 if start_offset + 60 <= timeline.get('end_offset', 0) else start_offset + 30
        timelines[index] = {
            'status': 'selected',
            'title': '현재 예약',
            'start_offset': start_offset,
            'end_offset': end_offset,
        }
        if end_offset < timeline.get('end_offset', 0):
            timelines.insert(index + 1, {
                'status': 'available',
                'title': '예약 가능',
                'start_offset': end_offset,
                'end_offset': timeline.get('end_offset', 0),
            })
        return True
    return False
