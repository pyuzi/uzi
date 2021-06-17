from types import ModuleType
import typing as t
from djx.common.imports import ImportPath
from ninja import *
from ninja.constants import NOT_SET

# from djx.schemas import Schema, GenericSchema

from .renderers import JSONRenderer, BaseRenderer

BaseAPI = NinjaAPI
del NinjaAPI


def include_router(module: t.Union[str, ImportPath, ModuleType], path: str='routers'):
    module = ImportPath(module)
    r1 = ImportPath(module, path or 'routers')(None)
    if r1 is None:
        if path == 'routers':
            return ImportPath(module, 'router')()
        raise LookupError(f'router not defined in {module}')

    return r1



class API(BaseAPI):
    
    def __init__(self, *args, renderer: BaseRenderer=None, **kwds):
        super().__init__(*args, renderer=renderer or JSONRenderer(), **kwds)

    def add_router(self, prefix: str, router: t.Union[Router, list, tuple], **kwds) -> None:
        if isinstance(router, (list, tuple)):
            for p, r in router:
                self.add_router(prefix + p, r, **kwds)
        else:
            super().add_router(prefix, router, **kwds)


    def add_routers(self, *routers: tuple[str, Router], tags: list[str]=None) -> None:
        for p, r in routers:
            self.add_router(p, r, tags=tags)



class Router(Router):

    def add_api_operation(self, path: str, methods: list[str], view_func: t.Callable, **kwds: t.Any):
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





