
from types import ModuleType
import typing as t
from jani.common.imports import ImportRef
from jani.di import ioc
from ninja import *
from ninja.constants import NOT_SET

from .const import *

from django.http.request import HttpRequest
from django.http.response import HttpResponseBase as HttpResponse


from jani.di import ioc
from jani.abc import api as abc


abc.Request.register(HttpRequest)
abc.Response.register(HttpResponse)

ioc.alias(HttpRequest, abc.Request, at='request')

# from jani.schemas import Schema, GenericSchema

from .renderers import JSONRenderer, BaseRenderer
from .parsers import Parser, JSONParser




BaseAPI = NinjaAPI
del NinjaAPI


def include_router(module: t.Union[str, ImportRef, ModuleType], path: str=None):
    module = ImportRef(module)
    r1 = ImportRef(module, path or 'routers')(None)
    if r1 is None:
        if path is None:
            return ImportRef(module, 'router')()
        raise LookupError(f'router not defined in {module}')

    return r1


@ioc.value(at='main', use=None, cache=True)
class API(BaseAPI):
    
    def __init__(self, *args, renderer: BaseRenderer=None, parser: Parser=None, **kwds):
        kwds['parser'] = parser or JSONParser()
        kwds['renderer'] = renderer or JSONRenderer()
        super().__init__(*args, **kwds)
        set_default_exc_handlers(self)

    def add_router(self, prefix: str, router: t.Union[Router, list, tuple], **kwds) -> None:
        if isinstance(router, (list, tuple)):
            for p, r in router:
                self.add_router(prefix + p, r, **kwds)
        elif isinstance(router, dict):
            for p, r in router.items():
                self.add_router(prefix + p, r, **kwds)
        else:
            if callable(router):
                router = router()
            if isinstance(router, str):
                router = ImportRef(router)()
            super().add_router(prefix, router, **kwds)


    def add_routers(self, *routers: t.Union[ImportRef, Router], tags: list[str]=None) -> None:
        self.add_router('', routers, tags=tags)



api: API = ioc.proxy(API)



class Router(Router):

    def __init__(self, *, 
                auth: t.Any=NOT_SET, 
                tags: t.Optional[list[str]]=None, 
                include_in_schema: bool = None) -> None:
        super().__init__(auth=auth, tags=tags)
        self.include_in_schema = include_in_schema

    def add_api_operation(self, path: str, methods: list[str], view_func: t.Callable, **kwds: t.Any):
        if self.include_in_schema is not None:
            kwds['include_in_schema'] = self.include_in_schema
        return super().add_api_operation(path, methods, view_func, **kwds)
    
    def add_router(self, prefix: str, router: t.Union[Router, list, tuple], **kwds) -> None:
        if isinstance(router, (list, tuple)):
            for p, r in router:
                self.add_router(prefix + p, r, **kwds)
        else:
            super().add_router(prefix, router, **kwds)

    def add_routers(self, *routers: tuple[str, Router], tags: list[str]=None) -> None:
        for p, r in routers:
            self.add_router(p, r, tags=tags)



from .errors import set_default_exc_handlers



