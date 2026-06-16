"""Shared DRF viewset helpers."""


class PublicReadViewSetMixin:
    """
    Skip JWT on safe HTTP methods (GET/HEAD/OPTIONS).

    DRF sets ``self.action`` only after ``initialize_request``, so checking
    ``self.action in {"list", "retrieve"}`` inside ``get_authenticators()`` does
    not work and expired Bearer tokens still produce 403 on public catalog reads.
    """

    def initialize_request(self, request, *args, **kwargs):
        self._public_read_request = request.method in ("GET", "HEAD", "OPTIONS")
        return super().initialize_request(request, *args, **kwargs)

    def get_authenticators(self):
        if getattr(self, "_public_read_request", False):
            return []
        return super().get_authenticators()
