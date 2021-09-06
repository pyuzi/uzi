import typing as t 
from djx.di import di


from djx.core.abc import Request

from django.template.backends import utils



@di.wrap()
def csrf_input(req: Request=None):
    if req is None:
        return None
    return utils.csrf_input(req)



@di.wrap()
def csrf_token(req: Request=None):
    if req is None:
        return None
    return utils.get_token(req)



@di.wrap()
def csrf_input_lazy(req: Request=None):
    if req is None:
        return None
    return utils.csrf_input_lazy(req)



@di.wrap()
def csrf_token_lazy(req: Request=None):
    if req is None:
        return None
    return utils.csrf_token_lazy(req)
    