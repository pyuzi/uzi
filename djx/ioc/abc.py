from abc import ABCMeta, abstractmethod
from collections import ChainMap
from collections.abc import Mapping, MutableSequence
from contextlib import AbstractContextManager
from types import FunctionType, GenericAlias, MethodType
from typing import Any, Callable, ClassVar, Protocol, Generic, Type, TypeVar, Union, overload, runtime_checkable

from flex.utils.decorators import export
from setuptools import depends


_T_CnSet = TypeVar('_T_CnSet')
_R_CnSet = TypeVar('_R_CnSet', bound=Any)
_T_Ctx = TypeVar('_T_Ctx', bound='Context')


@export()
class CanSetup(Generic[_T_CnSet], metaclass=ABCMeta):

    __slots__ = ()

    @abstractmethod
    def setup(self, obj: _T_CnSet) -> _R_CnSet:
        pass
    


@export()
class SupportsIndentity(metaclass=ABCMeta):

    __slots__ = ()




@export()
class StaticIndentity(SupportsIndentity):

    __slots__ = ()

    @abstractmethod
    def __hash__(self):
        return 0


StaticIndentity.register(str)
StaticIndentity.register(bytes)
StaticIndentity.register(int)
StaticIndentity.register(float)
StaticIndentity.register(tuple)
StaticIndentity.register(frozenset)





_IT = TypeVar("_IT")
_CV = TypeVar("_CV")
_IC = TypeVar("_IC", bound='InjectedContextManager')



@export()
class Injectable(SupportsIndentity, Generic[_IT]):

    __slots__ = ()


Injectable.register(type)
Injectable.register(MethodType)
Injectable.register(FunctionType)




@export()
class InjectedContextManager(Generic[_CV], metaclass=ABCMeta):
    
    __slots__ = ()

    __class_getitem__ = classmethod(GenericAlias)
    
    def __enter__(self) -> _CV:
        """Return `self` upon entering the runtime context."""
        return self

    @abstractmethod
    def __exit__(self, exc_type, exc_value, traceback):
        """Raise any exception triggered within the runtime context."""
        return None




@export()
class InjectableContextManager(Injectable[_IC], Generic[_CV, _IC]):
    __slots__ = ()
    



@export()
class Injector(InjectedContextManager, Mapping[Injectable[_IT], _IT]):
    __slots__ = ()








@export()
class Context(InjectedContextManager, CanSetup):
    
    __slots__ = ()

    name: str
    providers: Mapping
    caches: Mapping
    depends: list['Context']





@export()
class CanSetupContext(CanSetup[_T_Ctx]):
    __slots__ = ()

