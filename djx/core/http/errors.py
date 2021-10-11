import typing as t
from functools import partial
from collections.abc import MutableMapping, Sequence, Set
from djx.common.collections import fallbackdict
from djx.common.utils import text
from ninja.errors import *

try:
    from pydantic.error_wrappers import ValidationError as PydanticError
except ImportError:
    PydanticError = None



from django.http import Http404, HttpRequest, HttpResponse


from djx.common.exc import BaseError


def set_default_exc_handlers(api: 'API'):
    err_422 =  partial(_handle_error_exc, status=422, api=api)
    api.add_exception_handler(ValidationError, err_422)
    PydanticError and api.add_exception_handler(PydanticError, err_422)
    api.add_exception_handler(BaseError, partial(_handle_error_exc, api=api))





def _handle_error_exc(
    request: HttpRequest, exc: t.Union[ValidationError, PydanticError], api: "API", status=None
) -> HttpResponse:

    if not hasattr(exc, 'errors'):
        errors = list(_dump_validation_err(exc))
    elif callable(exc.errors):
        errors = [e for e in _dump_validation_err(exc.errors())]
    else:
        errors = [e for e in _dump_validation_err(exc.errors)]

    status = getattr(exc, 'status_code', None) or status or 400
    return api.create_response(request, errors, status=status)


def _dump_validation_err(err):
    if isinstance(err, (str, bytes)):
        yield dict(msg=err, type='error')
    elif isinstance(err, (Sequence, Set)):
        for e in err:
            yield from _dump_validation_err(e)
    elif err:

        if callable(getattr(err, 'dict', None)):
            err = fallbackdict(None, err.dict())
        elif isinstance(err, Exception):
            err = fallbackdict(msg=str(err), code=text.snake(err.__class__))
        else:
            err =fallbackdict(None, err)
        
        if 'path' not in err and isinstance((loc := err['loc']), Sequence):
            try:
                index = loc.index('body')
                err['path'] = loc[:index+1] + loc[index+2:]
            except ValueError:
                err['path'] = loc

        err.setdefault('code', err.get('type'))
        err.update(type='error')
        yield err

from . import API