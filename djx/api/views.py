import typing as t 

from collections.abc import Callable

from djx.common.utils import export
from djx.common.typing import get_all_type_hints, get_origin, get_args, eval_type

from djx.di import ioc, IocContainer
from djx.di.inspect import signature


from .common import ParamType

_T_Return = t.TypeVar('_T_Return')
T_ViewFuncion = Callable[..., _T_Return]



@export()
class View:

    __slots__ = 'func', 'methods', 'sig', 'params'

    def __init__(self, func: T_ViewFuncion):
        self.func = func
        self.sig = signature(func, evaltypes=True)
        self.params = dict()
        for name, param in self.sig.parameters.items():
            ann = ioc.is_provided(param.annotation)

    def run(self, req, *args, **kwds):
        try:
            
        except Exception as e:
            pass
        finally:
            pass
        
    def run(self, req, *args, **kwds):
        try:
            
        except Exception as e:
            pass
        finally:
            pass
        
    def __call__(self, req, *args, **kwds):
        with ioc.use('view'):
            return self.run(req, *args, **kwds)