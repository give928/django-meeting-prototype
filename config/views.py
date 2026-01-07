from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from common.decorators import json_login_required
from config.caches import MetricsCache, ReadmeCache
from config.metrics.cpu import get_cpu_usage
from config.metrics.gpu import get_gpu_usage
from config.metrics.memory import get_memory_usage
from config.metrics.task import get_task_count
from meetings.models import SpeechRecognition, Summarization


@login_required(login_url='sign-in')
def home(request):
    return render(request, 'home.html', {'readme': ReadmeCache.get()})


@login_required(login_url='sign-in')
def metrics(request):
    return render(request, 'metrics.html', {'metrics': MetricsCache.get()})


@json_login_required
def metrics_realtime(request):
    data = MetricsCache.get()

    data['cpu']['usage_percent'] = get_cpu_usage()
    data['memory'] = data['memory'] | get_memory_usage()
    data['gpu'] = data['gpu'] | get_gpu_usage()
    data['task'] = data['task'] | get_task_count()
    data['speech_recognition'] = SpeechRecognition.get_count()
    data['summarization'] = Summarization.get_count()

    return JsonResponse(data)
