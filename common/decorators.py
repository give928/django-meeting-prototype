from functools import wraps

from django.http import JsonResponse


def json_login_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
                return JsonResponse({'status': 'error', 'message': '로그인이 필요합니다.'}, status=401)
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path(), 'sign-in')
        return view_func(request, *args, **kwargs)

    return _wrapped_view
