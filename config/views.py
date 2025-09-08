from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required(login_url='sign-in')
def home(request):
    return render(request, 'home.html', {})
