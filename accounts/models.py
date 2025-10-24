from datetime import datetime

from django.contrib.auth.models import AbstractUser, Group
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from mptt.fields import TreeForeignKey
from mptt.models import MPTTModel

from .validators import UnicodeEmailValidator


class User(AbstractUser):
    class Position(models.TextChoices):
        PRO = 'PRO', _('프로')
        LEADER = 'LEADER', _('팀장')
        MPM = 'MPM', _('MPM')
        MANAGER = 'MANAGER', _('담당')
        DIRECTOR = 'DIRECTOR', _('상무')
        VICE_PRESIDENT = 'VICE_PRESIDENT', _('부사장')
        PRESIDENT = 'PRESIDENT', _('사장')

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    id = models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='id')
    password = models.CharField(max_length=128, verbose_name="password")
    email = models.CharField(error_messages={'unique': 'A user with that email already exists.'}, help_text='Required. 64 characters or fewer.', max_length=64, unique=True,
                             validators=[UnicodeEmailValidator()], verbose_name='email')
    username = models.CharField(max_length=64, verbose_name='username')
    first_name = models.CharField(blank=True, max_length=32, verbose_name='first name')
    last_name = models.CharField(blank=True, max_length=32, verbose_name='last name')
    position = models.CharField(blank=True, max_length=16, choices=Position.choices, default=Position.PRO, verbose_name='position')
    is_superuser = models.BooleanField(default=False, help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status')
    is_staff = models.BooleanField(default=False, help_text='Designates whether the user can log into this admin site.', verbose_name='staff status')
    is_leader = models.BooleanField(default=False, help_text='Designates whether the user is a leader on the team.', verbose_name='leader status')
    is_active = models.BooleanField(default=True, help_text='Designates whether this user should be treated as active. Unselect this instead of deleting accounts.', verbose_name='active')
    date_joined = models.DateTimeField(default=datetime.now, verbose_name="date joined")
    last_login = models.DateTimeField(blank=True, null=True, verbose_name='last login')
    groups = models.ManyToManyField(blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.', related_name='user_set', related_query_name='user', to='auth.group', verbose_name='groups')
    user_permissions = models.ManyToManyField(blank=True, help_text='Specific permissions for this user.', related_name='user_set', related_query_name='user', to='auth.permission', verbose_name='user permissions')

    def __str__(self):
        return f"{self.username} ({self.email})"

    class Meta:
        db_table = 'auth_user'


class Department(MPTTModel):
    group = models.OneToOneField(Group, on_delete=models.CASCADE, primary_key=True)
    parent = TreeForeignKey('self', blank=True, null=True, on_delete=models.SET_NULL, related_name='children', db_index=True, verbose_name='parent')
    is_active = models.BooleanField(default=True, verbose_name='enable')
    order = models.IntegerField(default=1, verbose_name='order')

    def __str__(self):
        return self.group.name

    def clean(self):
        super().clean()
        if self.parent and self.parent == self:
            raise ValidationError("A department cannot be its own parent.")

    class Meta:
        db_table = 'auth_department'
        # ordering = ['tree_id', 'lft']

    class MPTTMeta:
        order_insertion_by = ['order', 'group']