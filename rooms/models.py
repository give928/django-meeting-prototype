from django.core.cache import cache
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from common.models import Base


class Room(Base):
    id = models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='id')
    name = models.CharField(max_length=64, verbose_name='회의실')
    description = models.CharField(null=True, blank=True, max_length=1024, verbose_name='설명')
    seat_count = models.PositiveIntegerField(verbose_name='좌석수', validators=[
        MinValueValidator(1),
        MaxValueValidator(999),
    ])
    capacity_count = models.PositiveIntegerField(verbose_name='수용수', validators=[
        MinValueValidator(1),
        MaxValueValidator(999),
    ])
    has_monitor = models.BooleanField(default=True, verbose_name='화면공유')
    has_microphone = models.BooleanField(default=True, verbose_name='마이크')
    is_active = models.BooleanField(default=True, verbose_name='사용여부')

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        cache.delete('rooms')
