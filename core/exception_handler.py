import math

from rest_framework.exceptions import Throttled, ValidationError
from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return response

    if isinstance(exc, ValidationError) and isinstance(response.data, dict):
        response.data = {**response.data, 'codes': exc.get_codes()}
    elif isinstance(exc, Throttled):
        response.data = {
            'detail': str(exc.detail),
            'code': 'throttled',
            'retry_after': math.ceil(exc.wait) if exc.wait else None,
        }
    return response