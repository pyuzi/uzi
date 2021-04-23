from djx.common.collections import PriorityStack
import logging
from abc import ABCMeta, abstractmethod
from collections.abc import (
    Mapping, MutableSequence, ItemsView, ValuesView, MutableMapping, 
    Sequence, Hashable, Container, Callable
)
from collections import defaultdict
from contextlib import AbstractContextManager, ExitStack
from itertools import chain
from types import FunctionType, GenericAlias, MethodType
from typing import (
    Any, ClassVar, Iterable, Literal, Optional, Protocol,
    Generic, TYPE_CHECKING, Type, TypeVar, Union, cast, overload, runtime_checkable, 
)

from flex.utils.decorators import export
from flex.utils import text

from djx.common.abc import Orderable



__all__ = [
   
]


logger = logging.getLogger(__name__)


T = TypeVar("T")
T_co = TypeVar('T_co', covariant=True)  # Any type covariant containers.
T_Identity = TypeVar("T_Identity")
T_Injected = TypeVar("T_Injected")

T_Injector = TypeVar('T_Injector', bound='Injector', covariant=True)
T_Injectable = TypeVar('T_Injectable', bound='Injectable', covariant=True)

T_Injected_Ctx = TypeVar("T_Injected_Ctx", bound='InjectedContextManager')
T_Injected_CtxMan = TypeVar("T_Injected_CtxMan", bound='InjectedContextManager')

T_Context = TypeVar('T_Context', bound='InjectorContext')


_T_Setup = TypeVar('_T_Setup')
_T_Setup_R = TypeVar('_T_Setup_R')
_T_Scope = TypeVar('_T_Scope', bound='Scope', covariant=True)
_T_Conf = TypeVar('_T_Conf', bound='ScopeConfig', covariant=True)


T_Provider = TypeVar('T_Provider', bound='Provider', covariant=True)
T_Resolver = TypeVar('T_Resolver', bound='Resolver', covariant=True)

_T_Cache = MutableMapping['StaticIndentity', T_Injected]
_T_Providers = Mapping['StaticIndentity', Optional[T_Provider]]

_T_CacheFactory = Callable[..., _T_Cache]
_T_ContextFactory = Callable[..., T_Context]
_T_InjectorFactory = Callable[[_T_Scope, 'Injector'], T_Injector]


@export()
class ResolverFactory(ABCMeta,Generic[T_Resolver]):
    """ResolverFactory Object"""
    __slots__ = ()

    # def __class_getitem__(cls, params):
    #     if isinstance(params, (list, type(...))):
    #         return Callable.__class_getitem__(cls, (params, T_Resolver))
    #     else:
    #         return Callable.__class_getitem__(cls, params)
    
    @classmethod
    def __subclasshook__(cls, C):
        if cls is ResolverFactory:
            return hasattr(C, '__call__')
        return NotImplemented



@export()
class Resolver(Callable[[T_Injector], T_Injected], Generic[T_Injectable, T_Injected, T_Injector], metaclass=ResolverFactory):
    """Resolver Object"""
    __slots__ = ()

    @abstractmethod
    def __call__(self, inj: T_Injector) -> T_Injected: ...
    
    @classmethod
    def __subclasshook__(cls, C):
        if cls is Resolver:
            return hasattr(C, '__call__')
        return NotImplemented





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
            return hasattr(C, 'setup')
        return NotImplemented


@export()
class CanTeardown(Generic[_T_Setup], metaclass=ABCMeta):

    __slots__ = ()

    def setup(self, obj: _T_Setup):
        return obj

    @abstractmethod
    def teardown(self, *obj: _T_Setup):
        pass
    
    @classmethod
    def __subclasshook__(cls, C):
        if cls is CanTeardown:
            return hasattr(C, 'teardown')
        return NotImplemented




@export()
class CanSetupAndTeardown(CanSetup[_T_Setup, _T_Setup_R], CanTeardown[_T_Setup], Generic[_T_Setup, _T_Setup_R]):

    __slots__ = ()
  
    @classmethod
    def __subclasshook__(cls, C):
        if cls is CanSetupAndTeardown:
            return hasattr(C, 'setup') and hasattr(C, 'teardown')
        return NotImplemented



@export()
class SupportsIndentity(Hashable):

    __slots__ = ()






@export()
class StaticIndentity(Orderable, SupportsIndentity, Generic[T_Identity]):

    __slots__ = ()



StaticIndentity.register(str)
StaticIndentity.register(bytes)
StaticIndentity.register(int)
StaticIndentity.register(float)
StaticIndentity.register(tuple)
StaticIndentity.register(frozenset)





@export()
class Injectable(SupportsIndentity, Generic[T_Injected]):

    __slots__ = ()


Injectable.register(str)
Injectable.register(type)
Injectable.register(tuple)
Injectable.register(MethodType)
Injectable.register(FunctionType)
Injectable.register(GenericAlias)




@export()
class InjectedContextManager(Generic[T_Injected_Ctx], metaclass=ABCMeta):
    
    __slots__ = ()

    __class_getitem__ = classmethod(GenericAlias)
    
    def __enter__(self: T_Injected_Ctx) -> T_Injected_Ctx:
        """Return `self` upon entering the runtime context."""
        return self

    @abstractmethod
    def __exit__(self, exc_type, exc_value, traceback):
        """Raise any exception triggered within the runtime context."""
        return None




@export()
class InjectableContextManager(Injectable[T_Injected_CtxMan], Generic[T_Injected_Ctx, T_Injected_CtxMan]):
    __slots__ = ()
    



@export()
class ScopeConfig(Orderable, Generic[T_Injector, T_Context], metaclass=ABCMeta):
    
    name: ClassVar[str]
    priority: ClassVar[int]
    is_abstract: ClassVar[bool]
    depends: ClassVar[Sequence[str]]
    embedded: ClassVar[bool]

    cache_factory: ClassVar[_T_CacheFactory]
    context_factory: ClassVar[_T_ContextFactory]
    injector_factory: ClassVar[_T_InjectorFactory]
   



@export()
@Injectable.register
@StaticIndentity.register
class ScopeAlias(GenericAlias):

    __slots__ = ()

    # def __init__(self, origin: 'ScopeType', args) -> None:
    #     if type(args) is ScopeAlias:
    #         args = args.__args__
    #     GenericAlias.__init__(self, origin, args)

    @property
    def name(self):
        return self.__args__[0]

    def __call__(self):
        return super().__call__(*self.__args__)

    def __eq__(self, other):
        if isinstance(other, GenericAlias):
            return isinstance(other.__origin__, ScopeType) and self.__args__ == other.__args__

    def __hash__(self):
        return hash((ScopeType, self.__args__))


@export()
@Orderable.register
class ScopeType(ABCMeta, Generic[_T_Scope, _T_Conf]):
    """
    Metaclass for Scope
    """
    __types: PriorityStack[str, _T_Scope] = PriorityStack()
    config: _T_Conf

    __class_getitem__ = classmethod(GenericAlias)
    
    @classmethod
    def __prepare__(mcls, cls, bases, **kwds):
        # check that previous enum members do not exist
        return dict(__instance__=None)  

    def __init__(cls: 'ScopeType[_T_Scope, _T_Conf]', name, bases, dct, **kwds):
        super().__init__(name, bases, dct, **kwds)

        assert cls.__instance__ is None, (
            f'Scope class should not define __instance__ attribute'
        )


    def _get_scope_name(cls: 'ScopeType[_T_Scope, _T_Conf]', val):
        return val.name if type(val) is ScopeAlias \
            else val.config.name if isinstance(val, ScopeType) \
            else text.snake(val) 

    def _is_abstract(cls: 'ScopeType[_T_Scope, _T_Conf]', val=None):
        return not hasattr(val or cls, 'config') or (val or cls).config.is_abstract

    def _make_implicit_type(cls, name):
        return cls.__class__(name, cls._implicit_bases(), dict())

    def __call__(cls, name, *args,  **kwds):
        if type(name) is cls:
            return name
        name = cls._get_scope_name(name)
        if name in ScopeType.__types:
            cls = ScopeType.__types[name]
        else:
            cls = cls._make_implicit_type(name)
        
        if cls.config.is_abstract:
            raise TypeError(f'Cannot create abstract scope {cls}')
        elif cls.__instance__ is not None:
            return cls.__instance__

        cls.__instance__ = type.__call__(cls, *args, **kwds)
        return cls.__instance__
  
    def __getitem__(cls, params=...):
        if type(params) is ScopeAlias:
            params = params.__args__
        elif isinstance(params, (ScopeType, str)):
            params = cls._get_scope_name(params)
        elif isinstance(params.__class__, ScopeType):
            params = cls._get_scope_name(params.__class__)
        elif params in (..., (...,), [...], Any, (Any,),[Any], (), []):
            params = ANY_SCOPE        
        return ScopeAlias(cls, params)

    def register(cls, subclass: type[T]) -> type[T]:
        super().register(subclass)
        cls._register_scope_type(subclass)
        return subclass

    def _register_scope_type(cls, subclass: type[T] = None) -> type[T]:
        if not cls._is_abstract(subclass):
            ScopeType.__types[cls._get_scope_name(subclass or cls)] = subclass or cls
        return cls

    def __order__(cls, self=...):
        return cls.config
        
    __gt__ = Orderable.__gt__
    __ge__ = Orderable.__ge__
    __lt__ = Orderable.__lt__
    __le__ = Orderable.__le__



ANY_SCOPE = 'any'
MAIN_SCOPE = 'main'
LOCAL_SCOPE = 'local'

@export()
class Scope(Orderable, CanSetupAndTeardown[T_Injector], Container, metaclass=ScopeType):
    
    __slots__ = ()

    config: ClassVar[_T_Conf]

    name: str
    providers: _T_Providers
    providerstack: 'PriorityStack[StaticIndentity, T_Provider]'
    peers: list['Scope']
    embedded: bool

    ANY: ClassVar[ANY_SCOPE] = ANY_SCOPE
    MAIN: ClassVar[MAIN_SCOPE] = MAIN_SCOPE
    LOCAL: ClassVar[LOCAL_SCOPE] = LOCAL_SCOPE

    context_factory: _T_ContextFactory

    __class_getitem__ = classmethod(ScopeType.__getitem__)

    def __init__(self) -> None:
        assert self.__class__.__instance__ is None, (
                f'Scope are singletons. {self.__instance__} already created.'
            )

    def ready(self) -> None:
        ...
    
    @classmethod
    def __order__(cls, self=...):
        return cls.config
       
    @classmethod
    @abstractmethod
    def _implicit_bases(cls):
        ...
  
    @abstractmethod
    def create(self, parent: 'Injector') -> T_Injector:
        ...

    def __reduce__(self) -> None:
        return self.__class__, self.name

    def __eq__(self, x) -> bool:
        if isinstance(x, ScopeType):
            return x is self.__class__
        elif isinstance(x, Scope):
            return x.__class__ is self.__class__
        else:
            return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__class__)


@export()
class CanSetupScope(CanSetup[_T_Scope]):
    __slots__ = ()




@export()
class CanSetupAndTeardownScope(CanSetupScope[_T_Scope], CanTeardown[_T_Scope]):
    __slots__ = ()




@export()
class Provider(Resolver, Orderable, CanSetupAndTeardownScope[_T_Scope], Generic[T_Injected, T_Injectable, _T_Scope], metaclass=ABCMeta):
    
    __slots__ = (
        'abstract', 'concrete', 'scope', 'cache', 
        'priority', 'options', 
    )
    
    _default_scope: ClassVar[str] = Scope.MAIN

    abstract: StaticIndentity[T_Injectable]

    scope: str
    priority: int
    concrete: T_Injected
    cache: bool
    options: dict

    @abstractmethod
    def __call__(self, inj: 'Injector') -> T_Injected:
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
class InjectorKeyError(KeyError):
    pass

@export()
class InjectorContext(Generic[T_Injector], metaclass=ABCMeta):

    __slots__ = ('injector', '__issetup')

    injector: T_Injector
    __issetup: bool

    def __init__(self, injector: T_Injector):
        self.injector = injector
        self.__issetup = None

    def __enter__(self) -> T_Injector:
        if self.__issetup is None:
            self.__issetup = bool(self.injector.setup())
        return self.injector

    def __exit__(self, *exc):
        if self.__issetup is True:
            self.__issetup = False
            self.injector.exitstack.__exit__(*exc)




@export()
class Injector(Generic[_T_Scope, T_Injected, T_Provider, T_Injector], metaclass=ABCMeta):

    __slots__ = ()

    scope: _T_Scope
    parent: T_Injector
    level: int
   
    @property
    @abstractmethod
    def head(self) -> T_Injector:
        return self

    @property
    def main(self) -> T_Injector:
        """The injector for 
        """
        return self[Scope[Scope.MAIN]]

    @property
    def local(self) -> T_Injector:
        return self[Scope[Scope.LOCAL]]

    @property
    @abstractmethod
    def context(self) -> InjectorContext[T_Injector]:
        return self

    @abstractmethod
    def setup(self: T_Injector) -> bool:
        ...
    
    @abstractmethod
    def close(self) -> bool:
        ...

    @abstractmethod
    def enter(self, cm: InjectedContextManager[T_Injected]) -> T_Injected:
        """Enters the supplied context manager.

        If successful, also pushes its __exit__ method as an exit callback and
        returns the result of the __enter__ method. 
        
        See also: `Injector.onexit()`
        """
        ...

    @abstractmethod
    def onexit(self, cb: Union[InjectedContextManager, Callable]):
        """Registers an exit callback. Exit callbacks are called when the 
        injector closes.

        Callback can be a context manager or callable with the standard 
        `ContextManager's` `__exit__` method signature.
        """
        ...

    @abstractmethod
    def __contains__(self, x: T_Injectable) -> bool: 
        ...

    @abstractmethod
    def __bool__(self) -> bool:
        ...

    @abstractmethod
    def __len__(self) -> int: 
        ...

    @abstractmethod
    def __getitem__(self, k: T_Injectable) -> T_Injected: 
        ...
    
    @abstractmethod
    def __setitem__(self, k: T_Injectable, val: T_Injected): 
        ...

    @abstractmethod
    def __delitem__(self, k: T_Injectable): 
        ...
   

