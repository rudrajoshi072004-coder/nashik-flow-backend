from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return response

    details = response.data
    response.data = {
        "success": False,
        "message": "Request failed",
        "data": None,
        "errors": details,
    }
    return response
