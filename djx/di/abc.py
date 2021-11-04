from functools import cache
import inspect
import typing as t
from weakref import WeakSet
from djx.common.collections import fallback_default_dict, orderedset, PriorityStack
from djx.common.utils import Void
import logging
from abc import ABCMeta, abstractmethod
from collections.abc import (
    Mapping, MutableSequence, ItemsView, ValuesView, MutableMapping, 
    Sequence, Hashable, Container, Callable
)
from collections import defaultdict, deque
from contextlib import AbstractContextManager, ExitStack
from itertools import chain
from types import FunctionType, GenericAlias, MethodType

from djx.common.utils import cached_class_property, cached_property, class_property, export, text

from djx.common.abc import Orderable
from djx.common.collections import frozendict
from djx.common.typing import GenericAlias as _GenericAlias

if t.TYPE_CHECKING:
    from . import IocContainer, KindOfProvider


__all__ = [
   
]


logger = logging.getLogger(__name__)


T = t.TypeVar("T")
T_co = t.TypeVar('T_co', covariant=True)  # t.Any type covariant containers.
T_Identity = t.TypeVar("T_Identity")
T_Injected = t.TypeVar("T_Injected")

T_Injector = t.TypeVar('T_Injector', bound='Injector', covariant=True)
T_Injectable = t.TypeVar('T_Injectable', bound='Injectable', covariant=True)


T_ContextStack = t.TypeVar('T_ContextStack', bound='InjectorContext', covariant=True)


_T_Setup = t.TypeVar('_T_Setup')
_T_Setup_R = t.TypeVar('_T_Setup_R')
T_Scope = t.TypeVar('T_Scope', bound='Scope', covariant=True)
_T_Conf = t.TypeVar('_T_Conf', bound='ScopeConfig', covariant=True)


T_Provider = t.TypeVar('T_Provider', bound='Provider', covariant=True)
T_Resolver = t.TypeVar('T_Resolver', bound='Resolver', covariant=True)

_T_Cache = MutableMapping['StaticIndentity', T_Injected]
_T_Providers = Mapping['Injectable', t.Optional[T_Provider]]

_T_CacheFactory = Callable[..., _T_Cache]
_T_ContextFactory = Callable[..., T_ContextStack]
_T_InjectorFactory = Callable[[T_Scope, 'Injector'], T_Injector]



@export()
class Resolver(t.Generic[T_Injected], metaclass=ABCMeta):
    """Resolver Object"""

    __slots__ = ('bound', 'value', '__weakref__')

    alias: t.ClassVar[bool] = False
    concrete = None
    bound: t.Union[T_Injector, None]
    value: t.Union[T_Injected, type(Void)]

    def __init__(self, value=Void, bound=None):
        self.value = value
        self.bound = bound

    def bind(self: T_Resolver, inj: T_Injector) -> T_Resolver:
        return self if inj is self.bound else self.clone(bound=inj)

    def clone(self: T_Resolver, *args, **kwds) -> T_Resolver: 
        kwds.setdefault('value', self.value)
        kwds.setdefault('bound', self.bound)
        return self.__class__(*args, **kwds)
    
    def __call__(self, *args, **kwds) -> T_Injected: 
        return self.value

    # def __str__(self) -> str: 
    #     value, bound = self.value, self.bound
    #     return f'{self.__class__.__name__}({bound=}, {value=!r})'

    def __repr__(self) -> str: 
        bound, value = self.bound, self.value #(self() if self.value is Void else self.value)
        return f'{self.__class__.__name__}({bound=!s}, {value=!r})'
    





@export()
class SupportsIndentity(Hashable):

    __slots__ = ()






@export()
class StaticIndentity(Orderable, SupportsIndentity, t.Generic[T_Identity]):

    __slots__ = ()



StaticIndentity.register(str)
StaticIndentity.register(bytes)
StaticIndentity.register(int)
StaticIndentity.register(float)
StaticIndentity.register(tuple)
StaticIndentity.register(frozenset)





@export()
class InjectableType(ABCMeta):

    @property
    @cache
    def _typ_cache(cls):
        return set()

    def register(cls, subclass):
        """Register a virtual subclass of an ABC.

        Returns the subclass, to allow usage as a class decorator.
        """
        cls._typ_cache.add(subclass)
        return super().register(subclass)




@export()
class Injectable(SupportsIndentity, t.Generic[T_Injected], metaclass=InjectableType):

    __slots__ = ()

    def __class_getitem__(cls, param):
        if isinstance(param, tuple):
            param = param[0]

        excl = {type, Callable, None}
        typs = tuple(t for t in cls._typ_cache if t not in excl)
        if isinstance(param, (type, _GenericAlias, GenericAlias, t.TypeVar)):
            ptyp = param
        else:
            ptyp = type(param)

        rv = t.Union[ptyp, type[param], Callable[[t.Any], param], t.Union[typs]]

        return rv

    # def __subclasshook__(cls, o):
    #     if cls is Injectable:
    #         return 


Injectable.register(str)
Injectable.register(type)
Injectable.register(tuple)
Injectable.register(t.TypeVar)
Injectable.register(MethodType)
Injectable.register(FunctionType)
Injectable.register(GenericAlias)
Injectable.register(_GenericAlias)




@export()
class ScopeConfig(Orderable, t.Generic[T_Injector, T_ContextStack], metaclass=ABCMeta):
    
    name: t.ClassVar[str]
    priority: t.ClassVar[int]
    is_abstract: t.ClassVar[bool]
    depends: t.ClassVar[Sequence[str]]
    embedded: t.ClassVar[bool]

    cache_factory: t.ClassVar[_T_CacheFactory]
    context_factory: t.ClassVar[_T_ContextFactory]
    injector_factory: t.ClassVar[_T_InjectorFactory]
   



@export()
@Injectable.register
@StaticIndentity.register
class ScopeAlias(GenericAlias):

    __slots__ = ()

    @property
    def name(self):
        return self.__args__[0]

    # def __str__(self):
    #     return self.__args__[0]

    def __call__(self):
        return super().__call__(*self.__args__)

    def __eq__(self, other):
        if isinstance(other, GenericAlias):
            return isinstance(other.__origin__, ScopeType) and self.__args__ == other.__args__

    def __hash__(self):
        return hash((ScopeType, self.__args__))


@export()
@Orderable.register
class ScopeType(ABCMeta, t.Generic[T_Scope, _T_Conf, T_Provider]):
    """
    Metaclass for Scope
    """
    __types: t.Final[PriorityStack[str, T_Scope]] = PriorityStack()
    __aliases: t.Final[dict[str, ScopeAlias]] = fallback_default_dict(lambda k: ScopeAlias(*k))

    # __registries: defaultdict[str, PriorityStack[Injectable, Provider]] = defaultdict(PriorityStack)
    
    config: _T_Conf

    Config: type[ScopeConfig]

    __class_getitem__ = classmethod(GenericAlias)

    # @classmethod
    # def __prepare__(mcls, cls, bases, **kwds):
    #     return dict(
    #         # __instance__=None, 
    #         __registry__=None,
    #     )  
            
    # def __init__(cls: 'ScopeType[T_Scope, _T_Conf]', name, bases, dct, **kwds):
    #     super().__init__(name, bases, dct, **kwds)

    #     assert cls.__instance__ is None, (
    #         f'Scope class should not define __instance__ attributes'
    #     )

    # @class_property
    # def all_providers(cls):
    #     return ScopeType.__registries

    # @property
    # def own_providers(cls):
    #     return cls.all_providers[cls.config.name]

    # def register_provider(cls, provider: T_Provider, scope: t.Union[str, ScopeAlias]=None, *, flush: bool=None) -> T_Provider:
    #     if scope.__class__ is not cls:
    #         scope = cls._get_scope_name(scope or provider.scope or cls)
    #         cls = cls._gettype(scope)
        
    #     flush is not False and cls.__instance__ and cls.__instance__.flush(provider.abstract)
    #     cls.own_providers[provider.abstract] = provider

    #     return provider

    def _get_scope_name(cls: 'ScopeType[T_Scope, _T_Conf]', val):
        return val.name if type(val) is ScopeAlias \
            else text.snake(val) if isinstance(val, str)\
            else None if not isinstance(val, ScopeType) or cls._is_abstract(val) \
            else val.config.name

    def _is_abstract(cls: 'ScopeType[T_Scope, _T_Conf]', val=None):
        return not hasattr(val or cls, 'config') or (val or cls).config.is_abstract

    def _make_implicit_type(cls, name):
        return cls.__class__(name, cls._implicit_bases(), dict())

    def _gettype(cls, name, *, create_implicit=True):
        if name in ScopeType.__types:
            return ScopeType.__types[name]
        elif name and create_implicit:
            return cls._make_implicit_type(name)
        else:
            return cls

    def _active_types(cls):
        return dict(ScopeType.__types)
        
    # def __call__(cls, scope=None, *args,  **kwds):
    #     if scope.__class__ is cls:
    #         return scope
        
    #     cls = cls._gettype(cls._get_scope_name(scope or cls))

    #     if cls.config.is_abstract:
    #         raise TypeError(f'Cannot create abstract scope {cls}')
    #     elif cls.__instance__ is not None:
    #         return cls.__instance__

    #     cls.__instance__ = type.__call__(cls, *args, **kwds)
    #     return cls.__instance__
  
    @cache
    def __getitem__(cls, params=...):
        if type(params) is ScopeAlias:
            params = params.__args__
        elif isinstance(params, (ScopeType, str)):
            params = cls._get_scope_name(params)
        elif isinstance(params, Injector):
            params = params.scope.name
        elif isinstance(params.__class__, ScopeType):
            params = cls._get_scope_name(params.__class__)
        elif params in (..., (...,), [...], t.Any, (t.Any,),[t.Any], (), []):
            params = ANY_SCOPE  
        
        return cls.__aliases[(cls, params)]

    def register(cls, subclass: 'ScopeType[T]') -> type[T]:
        super().register(subclass)
        cls._register_scope_type(subclass)
        return subclass

    def _register_scope_type(cls, klass: type[T] = None) -> type[T]:
        klass = klass or cls
        if not cls._is_abstract(klass):
            name = cls._get_scope_name(klass)
            # klass.__registry__ = ScopeType.__registries[name]
            ScopeType.__types[name] = klass
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
REQUEST_SCOPE = 'request'
COMMAND_SCOPE = 'command'

@export()
class Scope(Orderable, Container, metaclass=ScopeType):
    
    __slots__ = ()

    config: t.ClassVar[_T_Conf]

    name: str
    providers: 'PriorityStack[StaticIndentity, T_Provider]'
    peers: list['Scope']
    embedded: bool
    dependants: orderedset[T_Scope]


    ANY: t.ClassVar[ANY_SCOPE] = ANY_SCOPE
    MAIN: t.ClassVar[MAIN_SCOPE] = MAIN_SCOPE
    LOCAL: t.ClassVar[LOCAL_SCOPE] = LOCAL_SCOPE

    __class_getitem__ = classmethod(ScopeType.__getitem__)

    # def __init__(self) -> None:
    #     assert self.__class__.__instance__ is None, (
    #             f'Scope are singletons. {self.__instance__} already created.'
    #         )

    @cached_class_property
    def key(cls):
        return cls[cls.config.name] if not cls._is_abstract() else cls

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
    def flush(self, *keys: Injectable, all=False):
        ...

    @abstractmethod
    def prepare(self):
        ...

    @abstractmethod
    def create(self, parent: 'Injector') -> T_Injector:
        ...

    # @abstractmethod
    # def bootstrap(self, inj: T_Injector) -> T_Injector:
    #     ...

    @abstractmethod
    def dispose(self, inj: T_Injector) -> T_Injector:
        ...

    @abstractmethod
    def create_context(self, inj: T_Injector) -> T_ContextStack:
        ...

    @abstractmethod
    def add_dependant(self, scope: 'Scope'):
        ...
    
    @abstractmethod
    def has_descendant(self, scope: 'Scope') -> bool:
        """Check if a scope is a descendant of this scope. 
        """
        ...

    def __reduce__(self):
        return self.__class__, self.name

    def __eq__(self, x) -> bool:
        if isinstance(x, ScopeAlias):
            return x == self.key
        elif isinstance(x, (Scope, ScopeType)):
            return x.key == self.key
        else:
            return False

    def __hash__(self) -> int:
        return hash(self.key)





@export()
class ProviderLike(Callable[['IocContainer', T_Injectable], Resolver[T_Injectable]], t.Generic[T_Injected, T_Injectable]):

    __slots__ = ()

    @abstractmethod
    def __call__(self, ioc: 'IocContainer', token: T_Injectable) -> Resolver[T_Injected]:
        ...

    @classmethod
    def __subclasshook__(cls, subclass: type) -> bool:
        if cls is ProviderLike:
            return callable(call := getattr(subclass, '__call__', None)) \
                and len(inspect.signature(call, follow_wrapped=False).parameters) > 1
        return NotImplemented




@export()
@ProviderLike.register
class Provider(Orderable, t.Generic[T_Injected, T_Injectable, T_Resolver], metaclass=ABCMeta):
    
    __slots__ = ()
    
    scope: str
    priority: int
    concrete: T_Injected
    cache: bool

    kind: 'KindOfProvider'

    # @abstractmethod
    # def __getstate__(self):
    #     ...

    @abstractmethod
    def __setstate__(self, state):
        ...

    def replace(self, **kwds):
        rv = self.clone()
        rv.__setstate__(kwds)
        return rv        

    @abstractmethod
    def clone(self: T_Provider) -> T_Provider:
        ...
        
    @abstractmethod
    def flush(self, *tokens, scope: t.Union[T_Scope, None]=None, all: t.Union[bool, None]=None) -> int:
        ...
        
    @abstractmethod
    def __call__(self, token: T_Injectable, scope: T_Scope) -> Resolver[T_Injected]:
        ...

    def __str__(self) -> str:
        return f'{self.__class__.__name__}({self.abstract}, at="{self.scope}")'




T_UsingAlias = Injectable[T_Injected]
T_UsingValue = T_Injected

T_UsingFunc = T_UsingFunc = Callable[..., T_Injected]
T_UsingType = type[T_Injected]
T_UsingCallable = t.Union[T_UsingType, T_UsingFunc]

T_UsingFactory = Callable[[Injectable[T_Injected], Scope, Provider], Resolver[T_Injected]]
T_UsingResolver = Resolver[T_Injected]

T_UsingAny = t.Union[T_UsingCallable, T_UsingFactory, T_UsingResolver, T_UsingAlias, T_UsingValue]





@export()
class InjectorKeyError(KeyError):
    pass




@export()
class InjectorContext(ExitStack, Callable[..., T_ContextStack], t.Generic[T_Injector, T_ContextStack]):

    injector: T_Injector
    parent: T_ContextStack
    
    @abstractmethod
    def new_child(self, inj: T_Injector) -> T_ContextStack:
        ...
  
    @abstractmethod
    def wrap(self, cm, exit=None):
        ...

    @abstractmethod
    def on_entry(self, cb, /, *arg, **kwds):
        ...

    @abstractmethod
    def __enter__(self) -> T_Injector:
        ...

    @abstractmethod
    def __exit__(self, *exc):
        ...





@export()
class Injector(AbstractContextManager[T_Injector], t.Generic[T_Scope, T_Injected, T_Provider, T_Injector], metaclass=ABCMeta):

    __slots__ = ()

    scope: T_Scope
    parent: T_Injector
    level: int

    content: Mapping[T_Injectable, Resolver] 

    # @property
    # @abstractmethod
    # def final(self) -> T_Injector:
    #     return self

    @property
    def main(self) -> T_Injector:
        """The injector for the `main` scope.
        """
        return self[Scope[Scope.MAIN]]

    @property
    def local(self) -> T_Injector:
        """The injector for for the `main` scope.
        """
        return self[Scope[Scope.LOCAL]]

    @property
    def name(self) -> str:
        return self.scope.name
        
    @property
    @abstractmethod
    def context(self) -> InjectorContext[T_Injector]:
        """Get a reusable contextmanager for this injector.
        """
        ...

    @abstractmethod
    def boot(self: T_Injector) -> bool:
        ...
    
    @abstractmethod
    def destroy(self) -> bool:
        ...

    @abstractmethod
    def get(self, k: T_Injectable, default: T=None) -> t.Union[T_Injected, T]: 
        ...
    
    @abstractmethod
    def make(self, injectable: T_Injectable, /, *args, **kwds) -> T_Injected: 
        ...
    
    @abstractmethod
    def __call__(self, injectable: T_Injectable=None, /, *args, **kwds) -> T_Injected: 
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
   

