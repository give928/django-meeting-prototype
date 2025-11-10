from django import forms

from .models import Room


class RoomForm(forms.ModelForm):
    seat_count = forms.IntegerField(
        label='좌석',
        min_value=1,
        max_value=999,
    )
    capacity_count = forms.IntegerField(
        label='수용인원',
        min_value=1,
        max_value=999,
    )
    description = forms.CharField(
        label='설명',
        widget=forms.Textarea(attrs={
            'class': 'form-control h-100',
            'maxlength': 1024,
            'placeholder': '설명'
        }),
    )

    class Meta:
        model = Room
        fields = ('name', 'description', 'seat_count', 'capacity_count', 'has_monitor', 'has_microphone', 'is_active')
