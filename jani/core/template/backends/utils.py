import typing as t 
from jani.di import ioc


from jani.core.abc import Request

from django.template.backends import utils



@ioc.wrap()
def csrf_input(req: Request=None):
    if req is None:
        return None
    return utils.csrf_input(req)



@ioc.wrap()
def csrf_token(req: Request=None):
    if req is None:
        return None
    return utils.get_token(req)



@ioc.wrap()
def csrf_input_lazy(req: Request=None):
    if req is None:
        return None
    return utils.csrf_input_lazy(req)



@ioc.wrap()
def csrf_token_lazy(req: Request=None):
    if req is None:
        return None
    return utils.csrf_token_lazy(req)
    