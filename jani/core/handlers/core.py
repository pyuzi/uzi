import logging
import typing as t

from contextlib import contextmanager
from django.core.handlers.base import BaseHandler

from jani.common.functools import cached_property

from jani.di import get_ioc_container, REQUEST_SCOPE

from ..http import HttpResponse, HttpRequest

from jani.abc.api import Request


logger = logging.getLogger(__name__)


class InjectorContextHandler(BaseHandler):

    request_class: t.ClassVar[type[HttpRequest]] = None
    di_scope: t.ClassVar[str] = REQUEST_SCOPE
    ioc = get_ioc_container()
    
    def get_response(self, request: HttpRequest) -> HttpResponse:
        self._provide_request(request)
        return super().get_response(request)
    
    async def get_response_async(self, request: HttpRequest) -> HttpResponse:
        self._provide_request(request)
        return await super().get_response_async(request)

    def _provide_request(self, req: HttpRequest):
        self.ioc.injector[Request] = req 
        # .at(self.di_scope, default=None)
        # assert inj.scope is self._inj_scope, f'{inj.scope!r} is not {self._inj_scope!r}'
        
        