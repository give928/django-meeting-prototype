from django.db import models

from accounts.models import User


class Base(models.Model):
    created_user = models.ForeignKey(User, on_delete=models.RESTRICT, related_name='created_user_id', verbose_name='등록자')
    created_date = models.DateTimeField(auto_now_add=True, verbose_name='등록일시')
    last_modified_user = models.ForeignKey(User, on_delete=models.RESTRICT, related_name='last_modified_user_id', verbose_name='수정자')
    last_modified_date = models.DateTimeField(auto_now=True, verbose_name='수정일시')

    class Meta:
        abstract = True