from django.conf import settings


class HttpMethodOverrideMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == 'POST':
            _method = request.POST.get("_method")
            if _method:
                request.META[settings.CSRF_HEADER_NAME] = request.POST.get('csrfmiddlewaretoken')
                request._load_post_and_files()
                request.method = _method.upper()
                request.META['REQUEST_METHOD'] = _method
        return self.get_response(request)
