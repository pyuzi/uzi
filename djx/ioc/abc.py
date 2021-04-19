from abc import ABCMeta, abstractmethod
from collections.abc import (
    Mapping, MutableSequence, ItemsView, ValuesView, MutableMapping, 
    Sequence, Hashable, Container
)
from collections import defaultdict
from contextlib import AbstractContextManager
from djx.ioc.tests import providers
from itertools import chain
from types import FunctionType, GenericAlias, MethodType
from typing import Any, Callable, ClassVar, Iterable, Literal, Optional, Protocol, Generic, TYPE_CHECKING, Type, TypeVar, Union, overload, runtime_checkable
import typing

from flex.utils.decorators import export


__all__ = [
    'ANY_SCOPE',
    'MAIN_SCOPE',
]



_T_Injected = TypeVar("_T_Injected")
_T_Identity = TypeVar("_T_Identity")
_T_Injected_Ctx = TypeVar("_T_Injected_Ctx")
_T_Injected_CtxMan = TypeVar("_T_Injected_CtxMan", bound='InjectedContextManager')



_T_Setup = TypeVar('_T_Setup')
_T_Setup_R = TypeVar('_T_Setup_R')
_T_Scope = TypeVar('_T_Scope', bound='Scope')
_T_Conf = TypeVar('_T_Conf', bound='ScopeConfig')

_T_Injector = TypeVar('_T_Injector', bound='Injector')
_T_Provider = TypeVar('_T_Provider', bound='Provider')
_T_Injectable = TypeVar('_T_Injectable', bound='Injectable')


_T_Cache = MutableMapping['StaticIndentity', _T_Injected]
_T_Providers = Mapping['StaticIndentity', Optional[_T_Provider]]


ANY_SCOPE = '__any__'
MAIN_SCOPE = '__main__'
    


@export()
class CanSetup(Generic[_T_Setup, _T_Setup_R], metaclass=ABCMeta):

    __slots__ = ()

    def __class_getitem__(cls, params):
        if not isinstance(params, tuple):
            params = (params,)
        if len(params) == 1:
            return GenericAlias(cls, params + params)
        else:
            return GenericAlias(cls, params)


    @abstractmethod
    def setup(self, *obj: _T_Setup) -> _T_Setup_R:
        pass

    @classmethod
    def __subclasshook__(cls, C):
        if cls is CanSetup:
            return _check_methods(C, 'setup')
        return NotImplemented


@export()
class CanTeardown(Generic[_T_Setup], metaclass=ABCMeta):

    __slots__ = ()

    @abstractmethod
    def teardown(self, *obj: _T_Setup):
        pass
    
    @classmethod
    def __subclasshook__(cls, C):
        if cls is CanSetup:
            return _check_methods(C, 'teardown')
        return NotImplemented




@export()
class CanSetupAndTeardown(CanSetup[_T_Setup, _T_Setup_R], CanTeardown[_T_Setup], Generic[_T_Setup, _T_Setup_R]):

    __slots__ = ()
  
    @classmethod
    def __subclasshook__(cls, C):
        if cls is CanSetup:
            return _check_methods(C, 'setup', 'teardown')
        return NotImplemented




@export()
class SupportsOrdering(metaclass=ABCMeta):
    """SupportsOrdering Object"""

    @abstractmethod
    def __ge__(self, x) -> bool:
        return NotImplemented

    @abstractmethod
    def __gt__(self, x) -> bool:
        return NotImplemented

    @abstractmethod
    def __le__(self, x) -> bool:
        return NotImplemented

    @abstractmethod
    def __lt__(self, x) -> bool:
        return NotImplemented

    @abstractmethod
    def __eq__(self, x) -> bool:
        return NotImplemented


@export()
class SupportsIndentity(Hashable):

    __slots__ = ()






@export()
class StaticIndentity(SupportsIndentity, Generic[_T_Identity]):

    __slots__ = ()



StaticIndentity.register(str)
StaticIndentity.register(bytes)
StaticIndentity.register(int)
StaticIndentity.register(float)
StaticIndentity.register(tuple)
StaticIndentity.register(frozenset)





@export()
class Injectable(SupportsIndentity, Generic[_T_Injected]):

    __slots__ = ()


Injectable.register(type)
Injectable.register(MethodType)
Injectable.register(FunctionType)




@export()
class InjectedContextManager(Generic[_T_Injected_Ctx], metaclass=ABCMeta):
    
    __slots__ = ()

    __class_getitem__ = classmethod(GenericAlias)
    
    def __enter__(self: _T_Injected_Ctx) -> _T_Injected_Ctx:
        """Return `self` upon entering the runtime context."""
        return self

    @abstractmethod
    def __exit__(self, exc_type, exc_value, traceback):
        """Raise any exception triggered within the runtime context."""
        return None




@export()
class InjectableContextManager(Injectable[_T_Injected_CtxMan], Generic[_T_Injected_Ctx, _T_Injected_CtxMan]):
    __slots__ = ()
    



@export()
class ScopeConfig(Generic[_T_Injector], metaclass=ABCMeta):
    
    name: ClassVar[str]
    priority: ClassVar[int]
    injector_class: ClassVar[type[_T_Injector]]
    cache_class: ClassVar[type[_T_Cache]]
    depends: ClassVar[Sequence[str]]
    embed_only: ClassVar[bool]
    implicit: ClassVar[bool]




@export()
class Scope(SupportsOrdering, CanSetupAndTeardown[_T_Injector], Container, Generic[_T_Injector, _T_Conf, _T_Provider]):
    
    __slots__ = ()

    conf: ClassVar[_T_Conf]

    name: str
    providers: _T_Providers
    providerstack: 'PriorityStack[StaticIndentity, _T_Provider]'
    peers: list['Scope']
    embed_only: bool
    ANY: ClassVar[ANY_SCOPE] = ANY_SCOPE
    MAIN: ClassVar[MAIN_SCOPE] = MAIN_SCOPE

    def ready(self) -> None:
        pass
    
    @abstractmethod
    def create(self, parent: _T_Injector) -> _T_Injector:
        return self.conf.injector_class(self, parent)

@export()
class CanSetupSope(CanSetup[_T_Scope]):
    __slots__ = ()




@export()
class CanSetupAndTeardownSope(CanSetupSope[_T_Scope], CanTeardown[_T_Scope]):
    __slots__ = ()




@export()
class Provider(SupportsOrdering, CanSetupAndTeardownSope[_T_Scope], Generic[_T_Injected, _T_Injectable, _T_Scope], metaclass=ABCMeta):
    
    __slots__ = (
        'abstract', 'concrete', 'scope', 'cache', 
        'priority', 'options', 
    )
    
    _default_scope: ClassVar[str] = Scope.MAIN

    abstract: StaticIndentity[_T_Injectable]

    scope: str
    priority: int
    concrete: _T_Injected
    cache: bool
    options: dict

    @abstractmethod
    def provide(self, inj: 'Injector') -> _T_Injected:
        return NotImplemented

    def setup(self, scope: _T_Scope):
        """Setup provider in given scope.
        """
        pass

    def teardown(self, scope: _T_Scope):
        pass

    def __str__(self) -> str:
        return f'{self.__class__.__name__}({self.abstract}, at="{self.scope}")'



@export()
class Injector(InjectedContextManager, CanSetupAndTeardown, Mapping[Injectable[_T_Injected], _T_Injected], Generic[_T_Scope, _T_Injected, _T_Provider, _T_Injector]):

    __slots__ = ('scope', 'parent', 'cache', 'providers', '_entries', '_lvl')

    scope: _T_Scope
    parent: _T_Injector
    cache: _T_Cache[_T_Injected]
    providers: _T_Providers[_T_Provider]
    _entries: int
    _lvl: int

    def __init__(self, scope: _T_Scope, parent: _T_Injector) -> None:
        self.scope = scope
        self.parent = parent
        self._lvl = 0 if parent is None else parent._lvl + 1 
        self._entries = 0

    @property
    def is_ready(self):
        return self._entries > 0

    def setup(self: _T_Injector) -> _T_Injector:
        if self.is_ready:
            raise RuntimeError(f'Injector {self} has already setup')
        self.scope.setup(self)

    def teardown(self):
        if not self.is_ready:
            raise RuntimeError(f'Injector {self} has not been setup')
        self.scope.teardown(self)

    def __str__(self) -> str:
        lvl = self._lvl
        return f'{self.__class__.__name__}({lvl=}, {self.scope})'

    def __repr__(self) -> str:
        return f'<{self} parent={self.parent!r}>'

    def __contains__(self, x) -> bool:
        if isinstance(x, Scope):
            return x in self.scope or x in self.parent
        elif self.is_ready:
            return x in self.providers or x in self.parent
        else:
            return False

    def __bool__(self) -> bool:
        return self.is_ready and bool(getattr(self, 'providers', False))

    def __len__(self) -> bool:
        return len(self.providers)

    def __iter__(self) -> bool:
        return iter(self.providers)

    def __enter__(self):
        if self._entries == 0:
            self.parent.__enter__()
            self.setup()
        self._entries += 1
        return self

    def __exit__(self, *exc):
        if self._entries == 1:
            self.teardown()
            self.parent.__exit__(*exc)

        self._entries -= 1
        assert self._entries >= 0, f'Context exited more time than it was entered'







_T_Stack_K = TypeVar('_T_Stack_K')
_T_Stack_S = TypeVar('_T_Stack_S', bound=MutableSequence)
_T_Stack_V = TypeVar('_T_Stack_V', bound=SupportsOrdering)


@export()
class PriorityStack(dict[_T_Stack_K, _T_Stack_S], Generic[_T_Stack_K, _T_Stack_V, _T_Stack_S]):
    
    __slots__= ('stackfactory',)

    if TYPE_CHECKING:
        stackfactory: Callable[..., _T_Stack_S] = list[_T_Stack_V]

    def __init__(self, _stackfactory: Callable[..., _T_Stack_S]=list, /, *args, **kwds) -> None:
        self.stackfactory = _stackfactory or list
        super().__init__(*args, **kwds)

    @overload
    def remove(self, k: _T_Stack_K, val: _T_Stack_V):
        self[k:].remove(val)

    def setdefault(self, k: _T_Stack_V, val: _T_Stack_V) -> _T_Stack_V:
        stack = super().setdefault(k, self.stackfactory())
        stack or stack.append(val)
        return stack[-1]

    def copy(self):
        return type(self)(self.stackfactory, ((k, self[k:][:]) for k in self))
    
    __copy__ = copy

    get_all = dict[_T_Stack_K, _T_Stack_S].get
    def get(self, k: _T_Stack_K, default=None):
        try:
            return self[k]
        except (KeyError, IndexError):
            return default

    all_items = dict[_T_Stack_K, _T_Stack_S].items
    def items(self):
        return ItemsView[tuple[_T_Stack_K, _T_Stack_V]](self)

    def merge(self, __PriorityStack_arg=None, /, **kwds):
        
        if isinstance(__PriorityStack_arg, PriorityStack):
            items = chain(__PriorityStack_arg.all_items(), kwds.items())
        elif isinstance(__PriorityStack_arg, Mapping):
            items = chain(__PriorityStack_arg.items(), kwds.items())
        elif __PriorityStack_arg is not None:
            items = chain(__PriorityStack_arg, kwds.items())
        else:
            items = kwds.items()

        for k,v in items:
            stack = super().setdefault(k, self.stackfactory())
            stack.extend(v)
            stack.sort()

    replace = dict.update
    def update(self, __PriorityStack_arg=None, /, **kwds):
        if isinstance(__PriorityStack_arg, Mapping):
            items = chain(__PriorityStack_arg.items(), kwds.items())
        elif __PriorityStack_arg is not None:
            items = chain(__PriorityStack_arg, kwds.items())
        else:
            items = kwds.items()

        for k,v in items:
            self[k] = v

    all_values = dict[_T_Stack_K, _T_Stack_S].values
    def values(self):
        return ValuesView[_T_Stack_V](self)
        
    @overload
    def __getitem__(self, k: _T_Stack_K) -> _T_Stack_V: ...
    @overload
    def __getitem__(self, k: slice) -> _T_Stack_S: ...
    def __getitem__(self, k):
        if isinstance(k, slice):
            return super().__getitem__(k.start)
        else:
            return super().__getitem__(k)[-1]

    def __setitem__(self, k: _T_Stack_K, val: _T_Stack_V):
        stack = super().setdefault(k, self.stackfactory())
        stack.append(val)
        stack.sort()




def _check_methods(C, *methods):
    mro = C.__mro__
    for method in methods:
        for B in mro:
            if method in B.__dict__:
                if B.__dict__[method] is None:
                    return NotImplemented
                break
        else:
            return NotImplemented
    return True