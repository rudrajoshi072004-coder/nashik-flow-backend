from rest_framework.response import Response


def success_response(data=None, message="OK", status_code=200):
    payload = {
        "success": True,
        "message": message,
        "data": data if data is not None else {},
        "errors": None,
    }
    return Response(payload, status=status_code)
