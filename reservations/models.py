from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, Subquery, OuterRef

from accounts.caches import DepartmentCache
from accounts.models import User, Department
from common.mixins import PrefetchValidationMixin
from common.models import Base, CreatedBase
from config import settings
from rooms.models import Room


class Reservation(Base, PrefetchValidationMixin):
    id = models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='id')
    room = models.ForeignKey(Room, on_delete=models.RESTRICT, related_name='reservations', verbose_name='회의실')
    title = models.CharField(max_length=128, verbose_name='제목')
    description = models.CharField(null=True, blank=True, max_length=1024, verbose_name='설명')
    start_datetime = models.DateTimeField(verbose_name='시작 시간')
    end_datetime = models.DateTimeField(verbose_name='종료 시간')
    is_active = models.BooleanField(default=True, verbose_name='사용여부')
    attendees = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="Attendee",
        through_fields=("reservation", "user"),
        related_name="reservations",
        verbose_name="참석자"
    )

    class Meta:
        db_table = "reservations_reservation"
        verbose_name = "예약"
        verbose_name_plural = "예약 목록"
        indexes = [
            models.Index(fields=['room', 'start_datetime'], name='idx_reservation_01'),
        ]

    def __str__(self):
        return f"{self.title} ({self.start_datetime.astimezone()} ~ {self.end_datetime.astimezone()})"

    def can_edit(self, user):
        if user.is_superuser:
            return True

        if self.created_user_id == user.id:
            return True

        if self.exists_in_prefetched('attendees', user.pk):
            return True

        created_groups = set(self.created_user.groups.values_list('pk', flat=True))
        user_groups = set(user.groups.values_list('pk', flat=True))

        for created_group in created_groups:
            try:
                ancestors = (DepartmentCache.find_by_group_id(created_group)
                             .get_ancestors(include_self=True if user.is_leader else False))
                for ancestor in ancestors:
                    if ancestor.pk in user_groups:
                        return True
            except Department.DoesNotExist:
                continue

        return False

    def clean(self):
        super().clean()

        if self.end_datetime <= self.start_datetime:
            raise ValidationError({
                'end_datetime': '종료 일시는 시작 일시보다 이후여야 합니다.',
            })

        q = Q(room=self.room)
        if self.pk:
            q &= ~Q(pk=self.pk)
        q &= Q(start_datetime__lt=self.end_datetime, end_datetime__gt=self.start_datetime)
        q &= Q(is_active=True)

        reservation = (
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
            .first())
        if reservation is not None:
            message = (f'{self.start_datetime.astimezone().strftime("%Y-%m-%d %H:%M")} ~ {self.end_datetime.astimezone().strftime("%Y-%m-%d %H:%M")}\n시간에 이미 다른 예약이 있습니다.'
                       f'\n\n회의: {reservation.title}\n시간: {reservation.start_datetime.astimezone().strftime("%Y-%m-%d %H:%M")} ~ {reservation.end_datetime.astimezone().strftime("%Y-%m-%d %H:%M")}'
                       f'\n예약자: [{reservation.group_name}]{reservation.created_user.username}'
                       f'\n\n다른 시간으로 선택해주세요.')
            raise ValidationError({
                'start_datetime': message,
                'end_datetime': message,
            })

    def save_attendees(self, attendees: set[int], updated_user):
        existing_attendees = set(self.attendees.values_list('pk', flat=True))

        delete_attendees = existing_attendees - attendees
        insert_attendees = attendees - existing_attendees

        if delete_attendees:
            Attendee.objects.filter(reservation=self, user_id__in=delete_attendees).delete()

        new_attendees = [
            Attendee(reservation=self, user_id=user_id, created_user=updated_user)
            for user_id in insert_attendees
        ]
        if new_attendees:
            Attendee.objects.bulk_create(new_attendees, ignore_conflicts=True)

        return {
            "deleted": len(delete_attendees),
            "added": len(insert_attendees)
        }


class Attendee(CreatedBase):
    id = models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='id')
    reservation = models.ForeignKey(Reservation, on_delete=models.RESTRICT, related_name='reservation_attendee_set', verbose_name='예약')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name='reservation_attendee_set', verbose_name='사용자')

    class Meta:
        db_table = "reservations_attendee"
        verbose_name = "참석자"
        verbose_name_plural = "참석자 목록"
        unique_together = ("reservation", "user")

    def __str__(self):
        return f"{self.user} @ {self.reservation}"
