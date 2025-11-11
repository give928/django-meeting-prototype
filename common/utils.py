from django.core.handlers.wsgi import WSGIRequest


class RequestUtils:
    @staticmethod
    def get_client_ip(request: WSGIRequest) -> str:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    @staticmethod
    def get_page(request: WSGIRequest) -> int:
        try:
            page = request.GET.get('page', '1')
            return int(page)
        except Exception as e:
            return 1