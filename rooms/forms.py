from django import forms

from .models import Room


class RoomForm(forms.ModelForm):
    description = forms.CharField(
        label='설명',
        widget=forms.Textarea(attrs={
            'class': 'form-control h-25',
            'maxlength': 1024,
            'placeholder': '설명'
        })
    )

    class Meta:
        model = Room
        fields = ('name', 'description', 'capacity', 'has_monitor', 'has_microphone', 'is_active')
