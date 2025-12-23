import logging

from django.core.cache import cache

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
