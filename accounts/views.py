from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import render, redirect

import logging

from accounts.caches import DepartmentCache
from common.utils import RequestUtils

logger = logging.getLogger(__name__)


def sign_in(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        remember = request.POST.get('remember') == 'me'
        username = request.POST.get('username')

        if form.is_valid():
            user = form.get_user()
            last_login = user.last_login
            login(request, user)
            logger.info('User Signed in [%s] %s', RequestUtils.get_client_ip(request), username)
            next_url = request.GET.get('next')
            if last_login is not None:
                messages.success(request, f'{user} 님, 환영합니다!\n마지막 로그인: {last_login.astimezone().strftime("%Y년 %m월 %d일 %H시 %M분 %S초")}')
            else:
                messages.success(request, f'{user} 님, 환영합니다!')
            if next_url:
                return response_cookie(redirect(next_url), remember, username)
            return response_cookie(redirect('home'), remember, username)

        logger.warning('Failed to sign in [%s] %s', RequestUtils.get_client_ip(request), username)
        form.initial = {'username': username if remember else None}
        http_response = render(request, 'sign-in.html', {'form': form})
        return response_cookie(http_response, remember, username)

    return render(request, 'sign-in.html', {'form': AuthenticationForm(request, initial={"username": request.COOKIES.get('username')})})


def response_cookie(http_response, remember, username):
    if remember is True and username is not None:
        http_response.set_cookie('username', value=username, httponly=True)
    else:
        http_response.delete_cookie('username')

    return http_response


def sign_out(request):
    auth_logout(request)
    return redirect('sign-in')


@login_required(login_url='sign-in')
def departments(request):
    return render(
        request,
        'accounts/departments.html',
        {
            'departments': DepartmentCache.find(is_active=True)
        })