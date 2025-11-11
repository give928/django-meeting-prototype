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