import logging
import typing as t
import operator

from functools import cache, partial, update_wrapper
from contextvars import ContextVar
from collections.abc import Callable
from contextlib import AbstractContextManager, contextmanager
from cachetools.keys import hashkey

from djx.common.proxy import Proxy, unproxy
from djx.common.utils import export


from .scopes import Scope
from . import abc

from .container import ioc


from .abc import (
    ANY_SCOPE, LOCAL_SCOPE, MAIN_SCOPE, REQUEST_SCOPE, COMMAND_SCOPE,
    Injectable, InjectorKeyError, ScopeAlias, StaticIndentity, 
    T, T_Injected, T_Injector, T_Injectable
)

if not t.TYPE_CHECKING:
    __all__ = [
        'ANY_SCOPE',
        'LOCAL_SCOPE', 
        'MAIN_SCOPE',
        'REQUEST_SCOPE', 
        'COMMAND_SCOPE',
    ]


logger = logging.getLogger(__name__)



@export()
class InjectedProperty(t.Generic[T_Injected]):
    
    __slots__ = 'token', 'ioc', 'cache', '__name__', '_default', '__weakref__'

    token: tuple[type['InjectedProperty'], str, T_Injected]

    __name__: str
    cache: bool

    def __init__(self, dep: Injectable[T_Injected]=None, default: T_Injected=..., *, name=None, cache: bool=None, scope=None) -> T_Injected:
        self._default = default
        self.cache = bool(cache)
        self.ioc = unproxy(ioc)
        self.token = self.__class__, self.ioc.scope_name(scope, 'any'), dep,

        self.__name__ = name
        self._register()

    @property
    def depends(self):
        return self.token[2]

    @property
    def scope(self):
        return self.token[1]

    def __set_name__(self, owner, name):
        self.__name__ = name

        if self.depends is None:
            dep = t.get_type_hints(owner).get(name)
            if dep is None:
                raise TypeError(
                    f'Injectable not set for {owner.__class__.__name__}.{name}'
                )
            self.token = *self.token[:-1], dep

        self._register()

    def _register(self):   
        ioc = self.ioc
        token = self.token
        scope, dep = token[1:]
        ioc.is_provided(token, scope) or ioc.alias(token, dep, at=scope)

    def __get__(self, obj, typ=None) -> T_Injected:
        if obj is None:
            return self
        try:
            if not self.cache:
                return self.ioc.make(self.token)
            try:
                return obj.__dict__[self.__name__]
            except KeyError:
                val = self.ioc.make(self.token)

        except InjectorKeyError as e:
            if self._default is ...:
                raise AttributeError(self) from e
            return self._default
        else:
            return obj.__dict__.setdefault(self.__name__, val)

    def __str__(self) -> T_Injected:
        return f'{self.__class__.__name__}({self.token!r})'

    def __repr__(self) -> T_Injected:
        return f'<{self.__name__} = {self}>'






@export()
class InjectedClassVar(InjectedProperty[T_Injected]):

    def __get__(self, obj, typ=...) -> T_Injected:
        return super().__get__(typ, typ)


if t.TYPE_CHECKING:
    InjectedClassVar = t.Final[T_Injected]





T_Depends = t.TypeVar('T_Depends', bound=abc.Injectable, covariant=True)



class DependsAlias(t.GenericAlias):
    
    def __init__(self, origin, metadata):
            if isinstance(origin, DependsAlias):
                metadata = origin.__metadata__ + metadata
                origin = origin.__origin__
            super().__init__()
            self.__metadata__ = metadata

    def __hash__(self) -> bool:
        return super().__hash__()

    def copy_with(self, params):
        assert len(params) == 1
        new_type = params[0]
        return DependsAlias(new_type, self.__metadata__)

    def __repr__(self):
        return f"{self.__class__.__name__}[{t._type_repr(self.__origin__)}, {', '.join(repr(a) for a in self.__metadata__)}]"
        
    def __reduce__(self):
        return operator.getitem, (
            Depends, (self.__origin__,) + self.__metadata__
        )

    def __eq__(self, other):
        if not isinstance(other, DependsAlias):
            return NotImplemented
        if self.__origin__ != other.__origin__:
            return False
        return self.__metadata__ == other.__metadata__

    def __hash__(self):
        logger.info(f'Hashing {self.__class__.__name__}({self.__metadata__!r})')
        return hash((self.__origin__, self.__metadata__))




@export()
class Depends:

    """Annotates type as a `Dependency` that can be resolved by the di.
    
    Example: 
        Depends[t] # type(injector[t]) == t 
        
        Depends[InjectableType]
        Depends(typ, on=Injectable) # type(injector[Injectable]) = typ

        Depends(type, Scope['scope'], on=injectable) # type(injector[Scope('scope')][injectable]) == typ
        Depends(typ, Scope['scope']] ==  Depends[typ, typ, on='scope')  # type(injector[Scope('scope')][typ]) == typ 
    """
    __slots__ = '_on', '_at', # '__weakref__'


    # def __new__(cls):
    #     raise TypeError("Type Depends cannot be instantiated.")

    @cache
    def __new__(cls, type_: T_Depends, /, *, on: Injectable = ..., at: str =...) -> t.Annotated[T_Depends, 'Depends']:
        ann = object.__new__(cls)
        ann._on = on
        ann._at = at 

        try:
            ret = t.Annotated[type_, ann]
        except TypeError as e:
            raise TypeError(
                f'{cls.__name__}(type, /, *, on: Injectable = ..., at: str =...) '
                f'should be used with at least one type argument.'
            ) from e
        else:
            return ret


    def __class_getitem__(cls, params: t.Union[T, tuple[T, ...]]) -> t.Annotated[T, 'Dependency']:
        if not isinstance(params, tuple):
            tp = on = params
            at = ...
        else:
            tp, on, at, *_ = *params, ..., ...
        
        return cls(tp, on=on, at=at)
        

        scope = None
        if not isinstance(params, tuple):
            deps = ((tp := params),)
        elif(lp := len(params)) == 1:
            tp = (deps := params)[0]
        elif lp > 1:
            if isinstance(params[1], ScopeAlias):
                tp, scope, *deps = params
            else:
                tp, *deps = params
        

        deps or (deps := (tp,))
        isinstance(deps, list) and (deps := tuple(deps))
        _dep_types = (list, dict, Injectable, AnnotatedDepends)
        if any(not isinstance(d, _dep_types) for d in deps):
            raise TypeError("Depends[...] should be used "
                            "with at least one type argument and "
                            "an t.Optional ScopeAlias (Scope['name'])."
                            "and 1 or more Injectables if the type arg "
                            "is not the injectable")
        
        return DependsAlias(tp, (AnnotatedDepends(deps, scope=scope),))

    def __init_subclass__(cls, *args, **kwargs):
        raise TypeError(f"Cannot subclass {cls.__module__}.Depends")

    def __eq__(self, x) -> bool:
        if isinstance(x, Depends):
            return self._on == x._on and self._at == x._at
        return NotImplemented

    def __hash__(self) -> bool:
        return hash((self._on, self._at))

    def __repr__(self) -> bool:
        return f'{self.__class__.__name__}(on={self._on}, at={self._at})'







@export()
@Injectable.register
class AnnotatedDepends(t.Generic[T_Injectable, T_Injected]):
    """Dependency Object"""
    __slots__ = '_deps', '_scope', '_default', '__weakref__'

    def __new__(cls, deps: T_Injectable, scope: ScopeAlias=..., *, default: t.Any=...):
        if isinstance(deps, cls):
            if scope in (..., None, deps.scope) and default in (..., deps.default):
                return deps
            else:
                kwds = dict()
                scope in (..., None) or kwds.update(scope=scope)
                default is ... or kwds.update(default=default)
                return deps.copy(**kwds)
        return super().__new__(cls)

    def __init__(self, deps: T_Injectable, scope: ScopeAlias=..., *, default: t.Any=...):
        self._deps = tuple(deps) if isinstance(deps, list) \
            else deps if isinstance(deps, tuple) else (deps,)
        self._scope = Scope[(None if scope is ... else scope) or Scope.ANY]
        self._default = default
    
    @property
    def deps(self) -> T_Injectable:
        return self._deps

    @property
    def scope(self):
        return self._scope

    def __eq__(self, x) -> bool:
        if isinstance(x, AnnotatedDepends):
            return self._scope == x._scope and self._deps == x._deps
        return NotImplemented

    def __hash__(self) -> bool:
        # logger.info(f'Hashing {self.__class__.__name__}({self._scope!r}, {self._deps})')
        return hash((self.scope, self.deps))

    def __repr__(self) -> bool:
        return f'{self.__class__.__name__}({self._scope!r}, {self._deps})'

    def make_resolver(self, inj) -> T_Injectable:
        # return inj[self._scope][self._deps]
        inj = inj[self._scope]
        return next((inj[d] for d in self._deps), self._default)

    def copy(self, **kwds) -> T_Injectable:
        kwds['scope'] = kwds.get('scope') or self._scope
        kwds['deafult'] = kwds.setdefault('deafult', self._default)
        return self.__class__(self._deps, **kwds)
    __copy__ = copy
    

