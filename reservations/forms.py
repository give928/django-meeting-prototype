from django import forms

from accounts.models import User
from rooms.caches import RoomCache
from .models import Reservation


class RoomSelect(forms.Select):
    def __init__(self, *args, rooms_cache=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.rooms_cache = rooms_cache or {}

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        if hasattr(value, "value"):
            value = value.value
        if value and value in self.rooms_cache:
            option["attrs"]["data-seat"] = self.rooms_cache[value].seat_count
            option["attrs"]["data-capacity"] = self.rooms_cache[value].capacity_count
        return option


class ReservationForm(forms.ModelForm):
    description = forms.CharField(
        label='설명',
        widget=forms.Textarea(attrs={
            'class': 'form-control h-100',
            'maxlength': 1024,
            'placeholder': '설명'
        })
    )
    start_datetime = forms.DateTimeField(
        label='시작 일시',
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control', 'placeholder': '시작 일시', 'step': 1800})
    )
    end_datetime = forms.DateTimeField(
        label='종료 일시',
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control', 'placeholder': '종료 일시', 'step': 1800})
    )
    attendees = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="참석자"
    )

    class Meta:
        model = Reservation
        fields = ('room', 'title', 'description', 'start_datetime', 'end_datetime', 'attendees')

    def __init__(self, *args, readonly=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.readonly = readonly

        if self.instance.pk:
            self.fields['attendees'].initial = self.instance.attendees.all()
            self.fields['room'].initial = self.instance.room_id

        rooms = RoomCache.find()
        rooms_cache = {r.id: r for r in rooms}
        self.fields['room'].queryset = rooms
        self.fields['room'].widget = RoomSelect(
            choices=[(r.id, f'{r.name} ({r.seat_count}/{r.capacity_count}{" 🖥️" if r.has_monitor else ""}{" 🎤" if r.has_microphone else ""})') for r in rooms],
            attrs={'class': 'form-select'},
            rooms_cache=rooms_cache
        )

        if self.readonly:
            for field in self.fields.values():
                field.widget.attrs['readonly'] = True
                # if isinstance(field.widget, (forms.Select, forms.CheckboxSelectMultiple)):
                #     field.widget.attrs['disabled'] = True

    def clean(self):
        cleaned_data = super().clean()

        start = cleaned_data.get('start_datetime')
        end = cleaned_data.get('end_datetime')

        if start and end and end <= start:
            raise forms.ValidationError("종료 일시는 시작 일시보다 이후여야 합니다.")
