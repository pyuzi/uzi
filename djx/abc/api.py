
from logging import getLogger
import typing as t
from abc import ABC, ABCMeta, abstractmethod
from collections.abc import MutableMapping, Callable, Mapping, Collection, Iterator, Sequence
from djx.common.collections import MappingProxy, frozendict, Arguments, _T_Args, _T_Kwargs
from djx.common.utils import export
from djx.common import json


from djx.di import ioc


logger = getLogger(__name__)


_T = t.TypeVar('_T')



@export()
@ioc.injectable(at='request')
class Request(metaclass=ABCMeta):
    __slots__ = ()

    session: 'Session'
    user: 'User'




@export()
@ioc.injectable(at='main', cache=True)
class BodyParser(t.Generic[_T]):
    _warned = False
    def parse(self, body: str, default=...) -> _T:
        if not self.__class__._warned:
            logger.warning(f'{self.__class__.__name__!r} should not be implemented here {self.__class__.__module__!r}')
            self.__class__._warned = True
            
        try:
            if body:
                return json.loads(body)
            elif default is not ...:
                return default
        except json.JSONDecodeError:
            if default is ...:
                return body
            else:
                return default




@export()
class Query(Mapping[str, _T]):
    __slots__ = ()


@export()
class QueryList(Mapping[str, Sequence[_T]]):
    __slots__ = ()


@export()
class Args(Sequence):
    __slots__ = ()



@export()
class Kwargs(Mapping):
    __slots__ = ()




@export()
class Arguments(Arguments[_T_Args, _T_Kwargs]):
    
    __slots__ = ()

    __kwargsclass__: t.ClassVar[type[MappingProxy[str, _T_Kwargs]]] = MappingProxy

    # @property
    # @abstractmethod
    # def args(self) -> Args[_T_Args]:
    #     ...

    # @property
    # @abstractmethod
    # def kwargs(self) -> Kwargs[str, _T_Args]:
    #     ...

    # @t.overload
    # def __getitem__(self, key: str) -> _T_Kwargs:
    #     ...
    # @t.overload
    # def __getitem__(self, key: t.Union[int, t.SupportsIndex]) -> _T_Args:
    #     ...
    # @abstractmethod
    # def __getitem__(self, key: t.Union[str, int, t.SupportsIndex]) -> t.Union[_T_Args, _T_Kwargs]:
    #     ...

    # @abstractmethod
    # def __iter__(self) -> Iterator[t.Union[int, str]]:
    #     ...
    
    

@export()
class Form(Mapping):
    __slots__ = ()


@export()
class FormList(Mapping[str, Sequence[_T]]):
    __slots__ = ()


        
@export()
class RawBody(ABC, t.Generic[_T]):
    __slots__ = ()


# RawBody.register(str)
# RawBody.register(bytes)

        
@export()
class Body(ABC):
    __slots__ = ()

    
@export()
class Params(Mapping):
    __slots__ = ()

    
@export()
class Inputs(Mapping):
    __slots__ = ()


@export()
class Files(Mapping):
    __slots__ = ()



@export()
class Headers(Mapping):
    __slots__ = ()

        
@export()
class Cookies(Mapping):
    __slots__ = ()
    
    




@export()
class Response(metaclass=ABCMeta):
    __slots__ = ()




@export()
class Session(MutableMapping):
    __slots__ = ()




