import logging
import typing as t

from contextlib import contextmanager
from django.core.handlers.base import BaseHandler

from djx.common.utils import cached_property

from djx.di import di

from ..http import HttpResponse, HttpRequest

from .. import abc


logger = logging.getLogger(__name__)


class InjectorContextHandler(BaseHandler):

    request_class: t.ClassVar[type[HttpRequest]]
    injector_scope_name: t.ClassVar[str] = di.REQUEST_SCOPE

    @cached_property
    def _inj_scope(self):
        return di.Scope[self.injector_scope_name]()    

    def injector(self) -> di.Injector:
        return di.scope(self.injector_scope_name)
    
    def get_response(self, request: HttpRequest) -> HttpResponse:
        self._provide_request(request)
        return super().get_response(request)
    
    async def get_response_async(self, request: HttpRequest) -> HttpResponse:
        self._provide_request(request)
        return await super().get_response_async(request)

    def _provide_request(self, req: HttpRequest):
        inj = di.injector()
        assert inj.scope is self._inj_scope, f'{inj.scope!r} is not {self._inj_scope!r}'
        inj[self.request_class] = req
        inj[HttpRequest] = req
        inj[abc.Request] = req
    