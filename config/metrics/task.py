from django_q.models import Task, OrmQ, Schedule

from config.settings import Q_CLUSTER


def get_task():
    return {
        'worker_count': Q_CLUSTER['workers'],
        'limit_count': Q_CLUSTER['queue_limit'],
    }


def get_task_count():
    return {
        'progressing_count': OrmQ.objects.count(),
        'completed_count': Task.objects.count(),
        'schedule_count': Schedule.objects.count(),
    }