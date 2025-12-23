import base64
import pickle
from urllib.parse import quote
from wsgiref.util import FileWrapper

from django.core.handlers.wsgi import WSGIRequest
from django.http import HttpResponse, FileResponse


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


class ResponseUtils:
    @staticmethod
    def response_file_with_range(request, content_type, file_path, file_size, file_name=None):
        range_header = request.META.get('HTTP_RANGE')

        if not range_header:
            wrapper = FileWrapper(open(file_path, 'rb'))
            response = FileResponse(wrapper, content_type=content_type)
            response['Content-Length'] = file_size

            if request.GET.get('mode') != 'play' and file_name:
                encoded_filename = quote(file_name)
                response['Content-Disposition'] = f'attachment; filename="{encoded_filename}"; filename*=UTF-8\'\'{encoded_filename}'

            return response

        # Range 헤더 처리
        try:
            range_value = range_header.split('=')[1]

            start, end = range_value.split('-')
            start = int(start) if start else 0
            end = int(end) if end else file_size - 1

        except Exception:
            # Range 포맷 오류 시 400 Bad Request
            return HttpResponse('Invalid Range header', status=400)

        length = end - start + 1

        # 416 Range Not Satisfiable 방지
        if start >= file_size or end >= file_size:
            response = HttpResponse(status=416)  # Range Not Satisfiable
            response['Content-Range'] = f'bytes */{file_size}'
            return response

        # 부분 파일 응답 (206 Partial Content)
        with open(file_path, 'rb') as f:
            f.seek(start)
            response = HttpResponse(f.read(length), status=206, content_type=content_type)

        response['Content-Length'] = length
        response['Content-Range'] = f'bytes {start}-{end}/{file_size}'
        response['Accept-Ranges'] = 'bytes'  # Range 지원

        return response


class SerializationUtils:
    @staticmethod
    def deserialize_by_pickle(serialized_data: str) -> any:
        try:
            decoded_bytes = base64.b64decode(serialized_data.encode('utf-8'))

            deserialized_object = pickle.loads(decoded_bytes)

            return deserialized_object

        except Exception as e:
            return f"역직렬화 오류 발생: {e}"
