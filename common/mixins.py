from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse


class PrefetchValidationMixin:
    def has_prefetched_relation(self, relation_name: str) -> bool:
        return (
                hasattr(self, '_prefetched_objects_cache') and
                relation_name in self._prefetched_objects_cache
        )

    def exists_in_prefetched(self, relation_name: str, pk: int) -> bool:
        rel = getattr(self, relation_name)

        if self.has_prefetched_relation(relation_name):
            return any(obj.pk == pk for obj in rel.all())

        return rel.filter(pk=pk).exists()

class JsonLoginRequiredMixin(LoginRequiredMixin):
    def handle_no_permission(self):
        return JsonResponse({'status': 'error', 'message': '🚫 로그인 후 이용해 주세요.'}, status=401)