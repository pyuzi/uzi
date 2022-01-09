from functools import partial
import typing as t 


from types import GenericAlias, MethodDescriptorType, MethodType
from jani.common.imports import ImportRef
from jani.common.intervals import Bound
from jani.common.proxy import proxy

from jani.common.utils import export, cached_property
from jani.di import inspect, ioc


_T = t.TypeVar('_T')


_T_Func = t.Callable[[t.Any], _T]


from jani.schemas.decorator import _ExperimentValidatedFunction

if t.TYPE_CHECKING:
    from jani.schemas.decorator import ConfigType




@export()
class Action(t.Generic[_T]):

    _signature: inspect.Signature
    # func: _T_Func

    def __init__(self, 
                func: t.Callable[[t.Any], _T], 
                name: str = None,
                config: 'ConfigType'=None,
                doc: str=None,
            ):
        
        self.func = func
        self.__name__ = name or func.__name__
        self._config = config
        self.__doc__ = doc or func.__doc__
    
    @property
    def validated(self):
        try:
            return self._validated
        except AttributeError:
            self._validated = _ExperimentValidatedFunction(self, self._config)
            return self._validated

    @cached_property
    def __signature__(self):
        return inspect.signature(self.func)

    def __set_name__(self, owner, name):
        self.__name__ = name

    def __call__(_self, self, /, *args: t.Any, **kwds: t.Any) -> t.Any:
        return _self.__get__(self)(*args, **kwds)

    def as_view(self, ctrl, **kwds):

        def view(req, *args, **kwds):
            pass
