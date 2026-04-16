from rest_framework.renderers import JSONRenderer


class StandardizedJSONRenderer(JSONRenderer):
    """
    Wraps successful JSON responses in a standard envelope.
    Error responses are handled by the custom exception handler.
    """

    def render(self, data, accepted_media_type=None, renderer_context=None):
        response = renderer_context.get("response") if renderer_context else None
        if response is not None and response.status_code >= 400:
            return super().render(data, accepted_media_type, renderer_context)

        if data is None:
            data = {}

        if isinstance(data, dict) and {"success", "message", "data", "errors"}.issubset(data.keys()):
            return super().render(data, accepted_media_type, renderer_context)

        wrapped = {
            "success": True,
            "message": "OK",
            "data": data,
            "errors": None,
        }
        return super().render(wrapped, accepted_media_type, renderer_context)
