
import typing as t
from abc import ABCMeta, abstractmethod
from jani.common.utils import export


from jani.di import ioc



@export()
@ioc.injectable(at='main', cache=True, priority=-10)
class Settings(metaclass=ABCMeta):
    
    __slots__ = ()
    
    DEBUG = False
    TIME_ZONE = None



_T_Rendered = t.TypeVar('_T_Rendered')
@export()
class Renderable(t.Generic[_T_Rendered], metaclass=ABCMeta):

    __slots__ = ()

    @classmethod
    def __subclasshook__(cls, klass: type) -> bool:
        if cls is Renderable:
            return hasattr(klass, 'render') and callable(klass, 'render')
        return NotImplemented

    @abstractmethod
    def render(self, *args, **kwds) -> _T_Rendered:
        ...




