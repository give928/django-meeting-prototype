from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from common.decorators import json_login_required
from config.caches import MetricsCache
from config.metrics.cpu import get_cpu_usage
from config.metrics.gpu import get_gpu_usage
from config.metrics.memory import get_memory_usage
from config.metrics.task import get_task_count
from meetings.models import SpeechRecognition, Summarization


@login_required(login_url='sign-in')
def home(request):
    return render(request, 'home.html', {'metrics': MetricsCache.get()})

@json_login_required
def metrics(request):
    metrics = MetricsCache.get()

    metrics['cpu']['usage_percent'] = get_cpu_usage()
    metrics['memory'] = metrics['memory'] | get_memory_usage()
    metrics['gpu'] = metrics['gpu'] | get_gpu_usage()
    metrics['task'] = metrics['task'] | get_task_count()
    metrics['speech_recognition'] = SpeechRecognition.get_count()
    metrics['summarization'] = Summarization.get_count()

    return JsonResponse(metrics)