from typing import Any, Callable
from ninja import *

from djx.schemas import Schema, ModelSchema, GenericSchema, GenericModelSchema



class API(NinjaAPI):
    pass




class Router(Router):
    

    def add_api_operation(self, path: str, methods: list[str], view_func: Callable, **kwds: Any) -> None:
        return super().add_api_operation(path, methods, view_func, **kwds)