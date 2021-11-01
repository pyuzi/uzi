from contextlib import AbstractContextManager, contextmanager
from contextvars import ContextVar
from functools import update_wrapper, wraps
from logging import getLogger
import os
from types import FunctionType, GenericAlias, MethodType, new_class
import typing as t

from collections.abc import Callable, Mapping

from djx.common.collections import PriorityStack, fallback_default_dict, fallbackdict, nonedict
from djx.common.imports import ImportRef
from djx.common.proxy import proxy 
from djx.common.saferef import SafeRefSet
from djx.common.utils import export

from . import abc

from .abc import Injectable, ScopeAlias, T_Injectable, T_Injected


if t.TYPE_CHECKING:
    from . import Scope, Provider as Dependency, Injector


logger = getLogger(__name__)

IOC_CONTAINER_ENV_KEY = 'DI_IOC_CONTAINER'

_T = t.TypeVar('_T')
_T_Callable = t.TypeVar('_T_Callable', type, Callable, covariant=True)


@export()
class IocContainer:

    __slots__ = (
        'deps','dep_class', 
        'default_scope', 'base_scope', 'scopes', 'scope_aliases', 
        'main', 'root', 'ctxvar'
    )

    deps: fallback_default_dict[str, PriorityStack[abc.Injectable, 'Dependency']]
    dep_class: type['Dependency']
    
    base_scope:  type['Scope']
    scopes: fallbackdict[str, 'Scope']
    scope_aliases: fallbackdict[str, str]
    default_scope: str
    main: 'Injector' 
    root: 'Injector' 
    ctxvar: ContextVar['Injector']

    def __init__(self, 
                base_scope: type['Scope'],
                dep_class: type['Dependency'],
                default_scope: str, *,
                scope_aliases: t.Union[Mapping, None]=None,
                ctxvar=None,
                root: 'Injector'=None,
                main: 'Injector'=None,
                ):
        setattr = object.__setattr__
        setattr(self, 'base_scope', base_scope)
        setattr(self, 'dep_class', dep_class)

        setattr(self, 'deps', fallback_default_dict(self._new_dep_stack))
        setattr(self, 'scopes', fallbackdict(self._new_scope_instance))
        setattr(self, 'scope_aliases', fallbackdict(lambda k: k, scope_aliases or ()))
        setattr(self, 'default_scope', default_scope)

        setattr(self, 'ctxvar', ctxvar or ContextVar(f'{self.__class__.__name__}.{ctxvar}'))

        main is None or setattr(self, 'main', main)
        root is None or setattr(self, 'root', root)

    def current(self):
        return self.ctxvar.get(self.main)

    injector = property(current)

    def _new_scope_instance(self, name) -> 'Scope':
        aka = self.get_scope_name(name)
        if name == aka:
            if not name:
                raise KeyError(f'ivalid scope name {name!r}')

            cls = self.get_scope_class(name, create=False)
            if cls is self.base_scope:
                raise KeyError(f'ivalid scope name {name!r}')
            elif cls.config.is_abstract:
                raise TypeError(f'Cannot instantiate abstract scope: {cls}')

            return self.scopes.setdefault(name, cls(self))

        return self.scopes[aka]

    def _new_dep_stack(self, key) -> 'Scope':
        return PriorityStack()

    def get_scope_name(self, scope, default=...) -> str:
        if scope.__class__ is not str:
            scope = self.base_scope._get_scope_name(scope) \
                or (self.default_scope if default is ... else default)
        return self.scope_aliases[scope]

    def scopekey(self, key):
        return self.base_scope[self.get_scope_name(key)]

    def get_scope_class(self, scope,  *, create=True) -> type['base_scope']:
        return self.base_scope._gettype(scope, create_implicit=create)

    def _make_main_injector_(self):
        return self.scopes['main'].create(self.root)

    def _make_root_injector_(self):
        from .injectors import NullInjector
        return NullInjector()

    def __getattr__(self, name):
        if name == 'main':
            object.__setattr__(self, name, self._make_main_injector_())
            return self.main
        elif name == 'root':
            object.__setattr__(self, name, self._make_root_injector_())
            return self.root
        raise AttributeError(name)
        
    def __setattr__(self, name, val):
        getattr(self, name)
        AttributeError(f'cannot set readonly attribute {name!r} on {self.__class__.__name__}')

    def proxy(self, abstract: Injectable[T_Injected], *, default=..., callable: bool=None) -> T_Injected:
        if default is ...:
            def resolve() -> T_Injected:
                return self.injector.make(abstract)
        else:
            def resolve() -> T_Injected:
                return self.injector.get(abstract, default)
        
        return proxy(resolve, callable=callable)

    def at(self, *scopes: t.Union[str, ScopeAlias, type['Scope']], default=...):
        """Get the first available Injector for given scope(s).
        """
        return self.injector.at(*scopes, default=default)

    def make(self, key, *args, **kwds):
        return self.injector.make(key, *args, **kwds)

    def get(self, abstract: T_Injectable, default: _T = None, /, *args, **kwds):
        return self.injector.get(abstract, default, *args, **kwds)

    def call(self, func: Callable[..., _T], /, *args: tuple, **kwargs) -> _T:
        return self.injector.make(func, *args, **kwargs)

    @t.overload
    def wrap(self, cls: type[_T], /, *, scope: str=None, priority=-1, **kwds) -> type[_T]:
        ...
    @t.overload
    def wrap(self, func: Callable[..., _T], /, *, scope: str=None, priority=-1, **kwds) -> Callable[..., _T]:
        ...
    @t.overload
    def wrap(self, *, scope: str=None, priority=-1, **kwds) -> Callable[[_T_Callable], _T_Callable]:
        ...

    def wrap(self, func: _T_Callable =..., /, *, scope: str=None, **kwds) -> _T_Callable:
        scope = self.get_scope_name(scope, 'any')

        def decorate(fn):
            if isinstance(fn, (type, GenericAlias)):
                params: tuple[t.TypeVar] = getattr(fn, '__parameters__', ())
                
                if params:
                    bases = fn, t.Generic.__class_getitem__(params)
                else:
                    bases = fn, 

                class wrapper(*bases):
                    __slots__ = ()

                    def __new__(cls, *a, **kw):
                        return self.injector.make(cls, *a, **kw)
                    
                    def __init__(self, *a, **kw) -> None:
                        ...

                wrapper = update_wrapper(wrapper, fn, updated=())
            else:
                def wrapper(*a, **kw):
                    return self.injector.make(wrapper, *a, **kw)

                if isinstance(fn, (FunctionType, MethodType)):
                    wrapper = update_wrapper(wrapper, fn)
                elif isinstance(fn, Callable):
                    wrapper = update_wrapper(wrapper, fn, updated=())
                
            self.alias(wrapper, fn, scope=scope, **kwds)
            return wrapper
        
        if func is ...:
            return decorate
        else:
            return decorate(func)

    def use(self, inj: t.Union[str, ScopeAlias, 'Injector'] = 'main') -> AbstractContextManager['Injector']:
        return self._ctxmanager_(inj)

    @contextmanager
    def _ctxmanager_(self, inj: t.Union[str, ScopeAlias, 'Injector'] = 'main'):
        cur = self.injector
        token = None
        if self.scopekey(inj) not in cur:
            if isinstance(inj, abc.Injector):
                if cur is not inj[cur.scope]:
                    raise RuntimeError(f'{inj!r} must be a descendant of {cur!r}.')
                cur = inj
            else:
                cur = self.scopes[inj].create(cur)
            token = self.ctxvar.set(cur)

            if __debug__:
                logger.debug(f'set current: {cur!r}')

        try:
            with cur:
                yield cur
        finally:
            if __debug__ and token:
                logger.debug(f'reset current: {token.old_value!r} {id(token.old_value)!r}')
            token is None or self.ctxvar.reset(token)

    def __contains__(self, obj):
        deps = self.deps
        scope, key, f = self._unslice_key(obj)
        
        for sc in ((self.get_scope_name(scope),) if scope else deps):
            if key in deps[sc]:
                return True
        return False
    
    def __getitem__(self, key) -> 'Dependency':
        scope, key, flags = self._unslice_key(key)
        # if key is None:
            # return self.deps[self.get_scope_name(scope)]
        return self.deps[self.get_scope_name(scope)][key]

    def __setitem__(self, key, val: 'Dependency'):
        if not isinstance(val, self.dep_class):
            TypeError(f'expected {self.dep_class}. got {type(val)}.')
        
        scope, key, flags = self._unslice_key(key)
        
        self.deps[self.get_scope_name(scope)].append(key, val)
        
    def __delitem__(self, key):
        scope, key, flags = self._unslice_key(key)
        if isinstance(key, abc.Provider):
            if scope is None:
                for s, d in self.deps.items():
                    if key.abstract in d:
                        if key in d[key.abstract:]:
                            scope = s
                            break
            else:
                scope = self.get_scope_name(scope)
            dep = key
            key = dep.abstract
        else:
            scope = self.get_scope_name(scope)
            dep = None

        if dep and scope in self.deps and dep in self.deps[scope][key:]: 
            self.deps[scope].remove(key, dep)
        scope in self.scopes and self.scopes[scope].flush(key)

    def is_provided(self, obj, scope=None):
        return slice(scope, obj) in self

    @classmethod
    def _unslice_key(cls, key):
        if key.__class__ is slice:
            return (None if key.start == 0 else key.start), key.stop, key.step or 1
        else:
            return None, key, 1

    def make_dependency(self, dep: t.Union[dict, 'Dependency']) -> 'Dependency':
        if isinstance(dep, abc.Provider):
            return dep
        elif not isinstance(dep, dict):
            return self.dep_class.create(**dep)
        elif isinstance(dep, Mapping):
            return self.dep_class.create(**dict(dep))
        raise TypeError(f'Invalid type. expected {self.dep_class.__name__} or Mapping.')

    def register(self, 
                dep: t.Union[dict, 'Dependency'], 
                scope: t.Union[str, ScopeAlias]=None, 
                *, 
                flush: bool=None) -> 'Dependency':
        
        dep = self.make_dependency(dep)
        scope = scope or dep.scope

        if flush is not False:
            del self[scope:dep.abstract]

        self[scope:dep.abstract] = dep

        return dep

    @t.overload
    def alias(self, 
            abstract: Injectable, 
            alias: T_Injectable, 
            *, 
            priority: int = 1, 
            scope: str = None, 
            cache:bool=None, 
            **opts) -> T_Injectable:
        ...

    @t.overload
    def alias(self, 
            abstract: Injectable,
            alias: Ellipsis =...,
            *, 
            priority: int = 1, 
            scope: str = None, 
            cache:bool=None, 
            **opts) -> Callable[[T_Injectable], T_Injectable]:
        ...

    def alias(self, abstract: Injectable, alias: T_Injectable=..., **kwds):
        """Registers an `AliasProvider`
        """
        def register(aka: T_Injectable):
            self.register(dict(kwds, abstract=abstract, alias=aka))
            return aka

        if alias is ...:
            return register
        else:
            return register(alias)    

    @t.overload
    def value(self, 
            abstract: T_Injectable, 
            value: T_Injected, *, 
            priority: int = 1, 
            scope: str = None, 
            cache:bool=None, 
            **opts) -> T_Injected:
        ...
    @t.overload
    def value(self, 
            abstract: T_Injectable, 
            # value: Ellipsis=..., 
            *, 
            priority: int = 1, 
            scope: str = None, 
            cache:bool=None, 
            **opts) -> Callable[[T_Injected], T_Injected]:
        ...

    def value(self, abstract: T_Injectable, value: T_Injected =..., **kwds):
        """Registers an `AliasProvider`
        """
        def register(val: T_Injected):
            self.register(dict(kwds, abstract=abstract, value=val))
            return val

        if value is ...:
            return register
        else:
            return register(value)    

    @t.overload
    def injectable(self, 
                    scope: str = None, *,
                    abstract: T_Injectable = None,
                    cache:bool=None, 
                    priority: int = 1,  
                    **opts) -> Callable[[T_Injectable], T_Injectable]:
        ...

    def injectable(self, scope: str = None, *, abstract: T_Injectable=None, **kwds):
        def register(factory: T_Injectable):
            self.register(dict(
                kwds,
                abstract=factory if abstract is None else abstract,
                factory=factory,
                scope=scope
            ))
            return factory

        return register


    @t.overload
    def provide(self, 
                abstract: T_Injectable, 
                *abstracts: T_Injectable, 
                factory: Callable=None,
                alias: abc.Injectable=None,
                value: t.Any=None,
                priority: int = 1, 
                scope: str = None, 
                cache: bool = None,
                **opts) -> T_Injectable: 
        ...
    @t.overload
    def provide(self, *, 
                factory: Callable=None,
                alias: abc.Injectable=None,
                value: t.Any=None,
                priority: int = 1, 
                scope: str = None, 
                cache: bool = None,
                **opts) -> Callable[[T_Injectable], T_Injectable]: 
        ...
    def provide(self, 
                abstract: T_Injectable=..., 
                *abstracts:T_Injectable, 
                **kwds):

        def register(_abstract):
            seen = set()
            for abstract in (_abstract, *abstracts):
                if abstract not in seen:
                    seen.add(abstract)
                    self.register(dict(kwds, abstract=abstract))
            return _abstract

        if abstract is ...:
            return register
        else:
            return register(abstract)







def _default_make_container():
    from .providers import Provider
    from .scopes import Scope
    return IocContainer(Scope, Provider, Scope.MAIN)




def _make_env_ioc():
    key = os.environ.get(IOC_CONTAINER_ENV_KEY, f'{__name__}:_default_make_container')
    rv = ImportRef(key)(None)
    if not isinstance(rv, IocContainer):
        if callable(rv):
            rv = rv()

        if not isinstance(rv, IocContainer):
            raise TypeError(
                f'ENV_KEY {IOC_CONTAINER_ENV_KEY} must be a path to an IocContainer. '
                f'{key!r} resolves to {type(rv)}'
            )
    return rv


ioc: IocContainer = export(proxy(_make_env_ioc, cache=True), name='ioc')
