from django.core.cache import cache
from .models import Room

import logging

logger = logging.getLogger(__name__)


class RoomCache:
    KEY = 'rooms'

    @classmethod
    def find(cls, is_active=None):
        try:
            rooms = cache.get(RoomCache.KEY)
            if rooms is None:
                raise RuntimeError('회의실 캐시 데이터가 없습니다.')
            logger.debug('Cache hit rooms')
        except Exception as e:
            logger.debug('Cache miss rooms')
            rooms = (Room.objects
                           .all())
            cache.set(RoomCache.KEY, rooms, 600)
            logger.debug('Cache set rooms: %s', rooms is not None)

        if is_active:
            rooms = rooms.filter(is_active=True)

        return rooms
