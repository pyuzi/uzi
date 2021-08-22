import typing as t
from functools import partial
from collections.abc import MutableMapping
from ninja.errors import *


from django.http import Http404, HttpRequest, HttpResponse


from djx.common.exc import BaseError


def set_default_exc_handlers(api: 'API'):
    api.add_exception_handler(ValidationError, partial(_default_validation_error, api=api))
    api.add_exception_handler(BaseError, partial(_default_error_res, api=api))


def _default_error_res(request: HttpRequest, exc: BaseError, api: "API", status=None):
    return api.create_response(
        request, exc.dict(), status=status or getattr(exc, 'http_status_code', 0) or 422
    )


def _default_validation_error(
    request: HttpRequest, exc: ValidationError, api: "API"
) -> HttpResponse:

    errors = [e for er in exc.errors for e in _dump_validation_err(er)]
    return api.create_response(request, dict(errors=errors), status=422)


def _default_validation_error(
    request: HttpRequest, exc: ValidationError, api: "API"
) -> HttpResponse:

    errors = [e for er in exc.errors for e in _dump_validation_err(er)]
    return api.create_response(request, dict(errors=errors), status=422)


def _dump_validation_err(err):
    if isinstance(err, (list, tuple)):
        for e in err:
            yield from _dump_validation_err(e)
        return

    if isinstance(err, str):
        err = dict(msg=err, type='error')
    elif isinstance(err, MutableMapping):
        if isinstance((loc := err.get('loc')), (tuple, list)):
            try:
                index = loc.index('body')
            except ValueError:
                pass
            else:
                err['loc'] = loc[:index+1] + loc[index+2:]
    
    yield err

from . import API