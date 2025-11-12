import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import RestrictedError
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views import View

from reservations.models import Reservation
from rooms.caches import RoomCache
from rooms.forms import RoomForm
from rooms.models import Room

logger = logging.getLogger(__name__)


@login_required(login_url='sign-in')
def rooms(request):
    return render(request, 'rooms/rooms.html', {'rooms': Room.objects.all()})


class RoomView(LoginRequiredMixin, View):
    form_class = RoomForm
    template_name = 'rooms/room.html'

    def get(self, request, *args, **kwargs):
        pk = kwargs['pk']
        if pk == 0:
            return render(request, self.template_name, {'form': self.form_class()})

        room = get_object_or_404(Room, pk=pk)
        return render(request, self.template_name, {'form': self.form_class(instance=room)})

    def post(self, request, *args, **kwargs):
        form = self.form_class(request.POST)
        if form.is_valid():
            room = form.save(commit=False)
            room.created_user_id = request.user.pk
            room.created_date = timezone.now()
            room.last_modified_user_id = request.user.pk
            room.last_modified_date = timezone.now()
            room.save()
            RoomCache.clear()
            messages.success(request, '회의실이 등록되었습니다.')
            return redirect('rooms')
        return render(request, self.template_name, {'form': form})

    def put(self, request, *args, **kwargs):
        pk = kwargs['pk']
        room = get_object_or_404(Room, pk=pk)
        form = self.form_class(request.POST, instance=room)
        if form.is_valid():
            room = form.save(commit=False)
            room.last_modified_user_id = request.user.pk
            room.last_modified_date = timezone.now()
            update_fields = ['name', 'description', 'seat_count', 'capacity_count', 'has_monitor', 'has_microphone', 'is_active', 'last_modified_user_id', 'last_modified_date']
            room.save(update_fields=update_fields)
            RoomCache.clear()
            messages.success(request, '회의실이 수정되었습니다.')
            return redirect('rooms')
        return render(request, self.template_name, {'form': form})

    def delete(self, request, *args, **kwargs):
        pk = kwargs['pk']
        room = get_object_or_404(
            Room.objects.only('id', 'name'),
            pk=pk
        )

        has_reservations = Reservation.objects.filter(room_id=pk).only('id').exists()
        if has_reservations:
            messages.error(request, f'{room.name} 회의실은 예약이 존재하여 삭제할 수 없습니다.')
            return redirect('rooms')

        try:
            room.delete()
            RoomCache.clear()
            messages.success(request, f'{room.name} 회의실이 삭제되었습니다.')
        except RestrictedError as e:
            related_objects = list(e.restricted_objects)
            messages.error(
                request,
                f'{room.name} 회의실은 {len(related_objects)}개의 예약이 연결되어 있어 삭제할 수 없습니다.'
            )
        except Exception as e:
            logging.error('회의실 삭제 중 예외 발생', e)
            messages.error(request, '회의실 삭제 중 예외가 발생했습니다.')

        return redirect('rooms')