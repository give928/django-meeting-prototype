import logging
import os

from django.core.cache import cache

from config import settings
from config.metrics.cpu import get_cpu
from config.metrics.gpu import get_gpu
from config.metrics.memory import get_memory
from config.metrics.os import get_os
from config.metrics.task import get_task

logger = logging.getLogger(__name__)


class MetricsCache:
    @classmethod
    def get(cls):
        key = 'metrics'
        try:
            metrics = cache.get(key)
            if metrics is None:
                raise RuntimeError('매트릭 캐시 데이터가 없습니다.')
            logger.debug('Cache hit metrics')
        except Exception as e:
            logger.debug('Cache miss metrics')
            metrics = MetricsCache._get_metrics()
            cache.set(key, metrics)
            logger.debug('Cache set metrics: %s', metrics is not None)

        return metrics

    @classmethod
    def _get_metrics(cls):
        cpu = get_cpu()
        memory = get_memory()
        gpu = get_gpu()
        os = get_os()
        task = get_task()

        return {
            "cpu": cpu,
            "memory": memory,
            "gpu": gpu,
            "os": os,
            "task": task,
        }

class ReadmeCache:
    @classmethod
    def get(cls):
        key = 'readme'
        try:
            readme = cache.get(key)
            if readme is None:
                raise RuntimeError('리드미 캐시 데이터가 없습니다.')
            logger.debug('Cache hit readme')
        except Exception as e:
            logger.debug('Cache miss readme')
            readme_path = os.path.join(settings.BASE_DIR, 'README.md')

            readme = ""
            if os.path.exists(readme_path):
                with open(readme_path, 'r', encoding='utf-8') as f:
                    readme = f.read()

            cache.set(key, readme, 3600)
            logger.debug('Cache set readme: %s', readme is not None)

        return readme
