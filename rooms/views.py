from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views import View

from rooms.caches import RoomCache
from rooms.forms import RoomForm
from rooms.models import Room


@login_required(login_url='sign-in')
def rooms(request):
    active_rooms = RoomCache.find()

    return render(request, 'rooms/rooms.html', {'rooms': active_rooms})


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
            room.is_active = True
            room.created_user_id = request.user.pk
            room.created_date = timezone.now()
            room.last_modified_user_id = request.user.pk
            room.last_modified_date = timezone.now()
            room.save()
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
            update_fields = ['name', 'description', 'seat_count', 'capacity_count', 'has_monitor', 'has_microphone', 'last_modified_user_id', 'last_modified_date']
            room.save(update_fields=update_fields)
            messages.success(request, '회의실이 수정되었습니다.')
            return redirect('rooms')
        return render(request, self.template_name, {'form': form})

    def delete(self, request, *args, **kwargs):
        pk = kwargs['pk']
        room = get_object_or_404(Room, pk=pk)
        room.is_active = False
        room.last_modified_user_id = request.user.pk
        room.last_modified_date = timezone.now()
        update_fields = ['is_active', 'last_modified_user_id', 'last_modified_date']
        room.save(update_fields=update_fields)
        messages.success(request, '회의실이 삭제되었습니다.')
        return redirect('rooms')
