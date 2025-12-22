from django import forms
from django.utils import timezone

from accounts.models import User
from .models import Meeting


class MeetingForm(forms.ModelForm):
    memo = forms.CharField(
        label='메모',
        widget=forms.Textarea(attrs={
            'class': 'form-control h-100',
            'maxlength': 1024,
            'placeholder': '메모'
        }),
        required=False,
    )
    start_datetime = forms.DateTimeField(
        label='시작 일시',
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control', 'placeholder': '시작 일시', 'step': 1800})
    )
    end_datetime = forms.DateTimeField(
        label='종료 일시',
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control', 'placeholder': '종료 일시', 'step': 1800}),
        required=False,
    )
    attendees = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="참석자",
    )
    is_open = forms.BooleanField(
        label='공개',
        required=False,
    )

    class Meta:
        model = Meeting
        fields = ('title', 'memo', 'start_datetime', 'end_datetime', 'is_open', 'attendees')

    def __init__(self, *args, readonly=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.readonly = readonly

        if self.instance.pk:
            self.fields['attendees'].initial = self.instance.attendees.all()
        else:
            now = timezone.now()
            self.fields['start_datetime'].initial = now.replace(minute=0 if now.minute < 30 else 30, second=0, microsecond=0)
            self.fields['is_open'].initial = False


    def clean(self):
        cleaned_data = super().clean()

        start = cleaned_data.get('start_datetime')
        end = cleaned_data.get('end_datetime')

        if start and end and end <= start:
            raise forms.ValidationError("종료 일시는 시작 일시보다 이후여야 합니다.")
