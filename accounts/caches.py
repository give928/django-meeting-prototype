from django.core.cache import cache
from .models import Department

import logging

logger = logging.getLogger(__name__)


class DepartmentCache:
    @classmethod
    def find(cls, is_active=None):
        key = 'departments'
        try:
            departments = cache.get(key)
            if departments is None:
                raise RuntimeError('부서 캐시 데이터가 없습니다.')
            logger.debug('Cache hit departments')
        except Exception as e:
            logger.debug('Cache miss departments')
            departments = (Department.objects
                           .select_related('group')
                           .prefetch_related('group__user_set')  # n+1
                           .all())
            cache.set(key, departments, 600)
            logger.debug('Cache set departments: %s', departments is not None)

        if is_active:
            departments = departments.filter(is_active=True)

        return departments

    @classmethod
    def find_by_group_id(cls, group_id):
        return DepartmentCache.find(is_active=None).filter(group_id=group_id)
