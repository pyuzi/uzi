from collections import deque
from contextlib import AbstractContextManager, contextmanager
from contextvars import ContextVar
from functools import update_wrapper
from logging import getLogger
import os
from threading import RLock
from types import FunctionType, GenericAlias, MethodType
import typing as t

from collections.abc import Callable, Mapping, Set, Iterable
from laza.common import text

from laza.common.collections import PriorityStack, fallback_default_dict, fallbackdict, frozendict
from laza.common.imports import ImportRef
from laza.common.proxy import proxy 
from laza.common.functools import export

from . import signals

from .common import (
    Depends,
    Injectable,
    InjectedLookup,
    InjectionToken,
    T_Injectable, T_Injected,
    KindOfProvider, InjectorVar,
)

from .typing import get_origin
from .scopes import ScopeAlias, Scope as BaseScope, MAIN_SCOPE
from .injectors import Injector
from .providers import (
    LookupProvider, Provider, AnnotationProvider, 
    UnionProvider, DependsProvider,
    T_UsingAny, T_UsingAny, 
    T_UsingAlias, T_UsingResolver, 
    T_UsingFactory, T_UsingFunc, 
    T_UsingType, T_UsingValue,
)




logger = getLogger(__name__)

IOC_CONTAINER_ENV_KEY = export('IOC_CONTAINER', name='IOC_CONTAINER_ENV_KEY')
IOC_SCOPES_ENV_KEY = export('IOC_SCOPES', name='IOC_SCOPES_ENV_KEY')


_T = t.TypeVar('_T')
_T_Callable = t.TypeVar('_T_Callable', type, Callable, covariant=True)
_T_Tags = t.Union[T_Injectable, Set[T_Injectable], dict[str, t.Union[T_Injectable, Set[T_Injectable]]]]
_T_ScopeNames = t.Union[str, Set[str]]


_T_InjectorKey = t.Union[type[T_Injected], Callable[..., T_Injected], InjectionToken[T_Injected]]

@export()
class IocContainer:

    __slots__ = (
        'providers', '_lock', '_onboot', 'bootstrapped',
        'default_scope', 'scopes', 'scope_aliases', 
        '_main', 'ctxvar',
    )

    providers: fallback_default_dict[str, PriorityStack[Injectable, Provider]]
    dep_class: type[Provider]

    _onboot: t.Union[deque[Callable[['IocContainer'], t.Any]], None]

    Scope:  t.ClassVar[type['BaseScope']] = BaseScope

    scopes: fallbackdict[str, 'BaseScope']
    scope_aliases: fallbackdict[str, str]
    default_scope: str
    main: 'Injector' 
    root: 'Injector' 
    ctxvar: ContextVar['Injector']
    signals: t.ClassVar = signals

    _non_providable: t.ClassVar[frozenset[Injectable]] = frozenset([None, type(None)])

    def __init__(self, 
                default_scope: str=MAIN_SCOPE, *,
                scope_aliases: t.Union[Mapping, None]=None,
                ctxvar=None):

        setattr = object.__setattr__
        setattr(self, '_lock', RLock())
        setattr(self, '_onboot', deque())
        setattr(self, 'bootstrapped', False)

        setattr(self, 'providers', fallback_default_dict(self._new_dep_stack))
        setattr(self, 'scopes', fallbackdict(self._new_scope_instance))
        setattr(self, 'scope_aliases', fallbackdict(lambda k: k, scope_aliases or ()))
        
        setattr(self, 'default_scope', default_scope)

        setattr(self, 'ctxvar', ctxvar or ContextVar(f'{self.__class__.__name__}.{ctxvar}', default=None))

    @property
    def main(self):
        try:
            return self._main
        except AttributeError:
            self.bootstrap()
            return self._main

    def current(self):
        return self.ctxvar.get() or self.main

    injector = property(current)

    def scope_name(self, scope, default=...) -> str:
        if scope.__class__ is not str:
            scope = self.Scope._get_scope_name(scope) \
                or (self.default_scope if default is ... else default)
        
        while scope != (aka := self.scope_aliases[scope]):
            scope = aka

        return scope

    def scopekey(self, key):
        return self.Scope[self.scope_name(key)]

    def get_scope_class(self, scope,  *, create=True) -> type['Scope']:
        return self.Scope._gettype(scope, create_implicit=create)

    def _make_main_injector_(self):
        return self.scopes['main'].create()

    def bootstrap(self):
        if self.bootstrapped:
            raise RuntimeError(f'{self.__class__.__name__} already bootstrapped.')
        
        with self._lock:
            setattr = object.__setattr__
            
            self.signals.setup.send(self.__class__, instance=self)
            
            self._register_default_providers_()
            self._run_onboot_callbacks(exhaust=True)

            self.signals.boot.send(self.__class__, instance=self)

            setattr(self, '_main', self._make_main_injector_())
            setattr(self, 'bootstrapped', True)

            self.signals.ready.send(self.__class__, instance=self)

    def _register_default_providers_(self):
        self.register(t.Union, UnionProvider(), at='any')
        self.register(t.Annotated, AnnotationProvider(), at='any')
        self.register(Depends, DependsProvider(), at='any')
        self.register(InjectedLookup, LookupProvider(), at='any')
        self.resolver({Injector, IocContainer}, lambda at: InjectorVar(at, at), at='any', priority=-10)

    def __setattr__(self, name, val):
        getattr(self, name)
        AttributeError(f'cannot set readonly attribute {name!r} on {self.__class__.__name__}')

    def proxy(self, tag: Injectable, *, default=..., callable: bool=None) -> T_Injected:
        if default is ...:
            def resolve() -> T_Injected:
                return self.injector.make(tag)
        else:
            def resolve() -> T_Injected:
                return self.injector.get(tag, default)
        
        return proxy(resolve, callable=callable)

    def at(self, *scopes: t.Union[str, ScopeAlias, type['Scope']], default=...):
        """Get the first available Injector for given scope(s).
        """
        return self.injector.at(*scopes, default=default)

    @t.overload
    def make(self, cls: type[T_Injected], *args, **kwds) -> T_Injected:
        ...
        
    @t.overload
    def make(self, key: Callable[..., T_Injected], *args, **kwds) -> T_Injected:
        ...
        
    @t.overload
    def make(self, token: InjectionToken[T_Injected], *args, **kwds) -> T_Injected:
        ...
        
    def make(self, key: _T_InjectorKey[T_Injected], *args, **kwds) -> T_Injected:
        return self.injector.make(key, *args, **kwds)

    def get(self, tag: T_Injectable, default: _T = None, /, *args, **kwds):
        return self.injector.get(tag, default, *args, **kwds)

    def call(self, func: Callable[..., _T], /, *args: tuple, **kwargs) -> _T:
        return self.injector.make(func, *args, **kwargs)

    @t.overload
    def inject(self, cls: type[_T], /, *, scope: str=None, priority=-1, **kwds) -> type[_T]:
        ...
    @t.overload
    def inject(self, func: Callable[..., _T], /, *, scope: str=None, priority=-1, **kwds) -> Callable[..., _T]:
        ...
    @t.overload
    def inject(self, *, scope: str=None, priority=-1, **kwds) -> Callable[[_T_Callable], _T_Callable]:
        ...

    def inject(self, func: _T_Callable =..., /, *, scope: str=None, **kwds) -> _T_Callable:
        scope = self.scope_name(scope, 'any')

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
                
            self.alias(wrapper, fn, at=scope, **kwds)
            return wrapper
        
        if func is ...:
            return decorate
        else:
            return decorate(func)

    def use(self, inj: t.Union[str, ScopeAlias, Injector] = 'main') -> AbstractContextManager[Injector]:
        return self._ctxmanager_(inj)

    @contextmanager
    def _ctxmanager_(self, inj: t.Union[str, ScopeAlias, Injector] = 'main'):
        cur = self.injector
        token = None
        if self.scopekey(inj) not in cur:
            if isinstance(inj, Injector):
                if cur is not inj[cur.scope]:
                    raise RuntimeError(f'{inj!r} must be a descendant of {cur!r}.')
                cur = inj
            else:
                cur = self.scopes[inj].create(cur)
            token = self.ctxvar.set(cur)

            # if __debug__:
            #     logger.debug(f'set current: {cur!r}')

        try:
            with cur:
                yield cur
        finally:
            # if __debug__ and token:
            #     logger.debug(f'reset current: {token.old_value!r} {id(token.old_value)!r}')
            token is None or self.ctxvar.reset(token)

    def on_boot(self, func: t.Union[Callable, None]=None, /, *args, **kwds):
        def decorate(fn):
            if self._onboot is None:
                return self._run_onboot_callback(fn, args, kwds)
            else:
                self._onboot.appendleft((fn, args, kwds))
                return fn

        if func is None:
            return decorate
        else:
            return decorate(func) 

    def _run_onboot_callbacks(self, *, exhaust=False):
        call = self._run_onboot_callback

        while self._onboot:
            call(*self._onboot.pop())

        exhaust is True and object.__setattr__(self, '_onboot', None)

    def _run_onboot_callback(self, cb: Callable, args=(), kwds=frozendict()):
        if not isinstance(cb, MethodType) or cb.__self__ is not self:
            return cb(self, *args, **kwds)
        else:
            return cb(*args, **kwds)

    def scope_booted(self, scope: 'Scope'):
        self.signals.boot.send(self.Scope, instance=scope, ioc=self)

    def scope_ready(self, scope: 'Scope'):
        self.signals.ready.send(self.Scope, instance=scope, ioc=self)
        
    def get_scope_aliases(self, scope: 'Scope', *, include_embeded=False):
        yield scope.name

        for aka, sc in self.scope_aliases.items():
            if self.scope_aliases[sc] == scope.name:
                yield aka
        
        if include_embeded:
            for e in scope.embeds:
                yield from self.get_scope_aliases(e, include_embeded=True)
            
    def _new_scope_instance(self, name) -> 'Scope':
        with self._lock:
            aka = self.scope_name(name)
            if name == aka:
                if not name:
                    raise KeyError(f'ivalid scope name {name!r}')

                cls = self.get_scope_class(name, create=False)
                if cls is self.Scope:
                    raise KeyError(f'ivalid scope name {name!r}')
                elif cls.config.is_abstract:
                    raise TypeError(f'Cannot instantiate tag scope: {cls}')
                
                self.scopes[name] = cls(self)
                return self.scopes[name]

            return self.scopes[aka]

    def _new_dep_stack(self, key) -> 'Scope':
        return PriorityStack()

    @classmethod
    def discover_scopes(cls, scopes: Iterable[str], ioc: 'IocContainer'=None):
        for scope in scopes:
            scope and ImportRef(scope)(None)
        
    def __contains__(self, obj):
        return self.injector.__contains__(obj)
    
    @t.overload
    def __getitem__(self, cls: type[T_Injected]) -> T_Injected:
        ...
        
    @t.overload
    def __getitem__(self, func: Callable[..., T_Injected]) -> T_Injected:
        ...
        
    @t.overload
    def __getitem__(self, token: InjectionToken[T_Injected]) -> T_Injected:
        ...
        
    def __getitem__(self, key: _T_InjectorKey[T_Injected]) -> T_Injected:
        return self.injector.__getitem__(key)

    def is_provided(self, obj, scope=None):
        if obj not in self._non_providable:
            scope = self.scope_name(scope, None)
            for dct in ((self.providers[scope],) if scope else self.providers.values()):
                if obj in dct:
                    return True
        return False

    def is_injectable(self, obj):
        if self.is_provided(obj):
            return True
        elif origin := get_origin(obj):
            if origin is t.Annotated:
                return any(self.is_injectable(a.__class__) for a in obj.__metadata__)
            elif origin in {t.Union, t.Literal}:
                return all(self.is_injectable(a) for a in obj.__args__)
            else:
                return self.is_injectable(origin)
        else:
            return False

    def flush(self, tag: T_Injectable, scope: str=None):
        scope = self.scope_name(scope)
        if scope := self.scopes.get(scope):
            scope.flush(tag)
    @t.overload
    def register(self, 
            tags: t.Union[_T_Tags, None],
            use: t.Union[Provider, T_UsingAny], /,
            at: t.Union[_T_ScopeNames, None] = None, 
            **kwds) -> None:
                ...

    def register(self, 
            provide: t.Union[_T_Tags, None] , /,
            use: t.Union[Provider, T_UsingAny], 
            at: t.Union[_T_ScopeNames, None] = None, 
            **kwds):
    
        if self.bootstrapped:
            self._register_provider(provide, use, at=at, **kwds)
        else:
            self.on_boot(self._register_provider, provide, use, at=at, **kwds)

    def create_provider(self, provider: t.Union[Provider, T_UsingAny], **kwds: dict) -> Provider:
        if isinstance(provider, Provider):
            if kwds:
                raise ValueError(f'got unexpected keyword arguments {tuple(kwds)}')
            return provider

        cls = self._get_provider_class(KindOfProvider(kwds.pop('kind')), kwds)
        return cls(provider, **kwds)

    def _get_provider_class(self, kind: KindOfProvider, kwds: dict) -> type[Provider]:
        return kind.default_impl

    def _register_provider(self, 
                tags: t.Union[_T_Tags, None],
                use: t.Union[Provider, T_UsingAny], /,
                at: t.Union[_T_ScopeNames, None] = None, 
                **kwds) -> None:
        
        provider = self.create_provider(use, **kwds)

        scope_name = self.scope_name

        if isinstance(at, Set):
            at = map(scope_name, at)
        else:
            at = scope_name(at),

        if tags is None:
            tags = provider.implicit_tag()
            if tags is NotImplemented:
                raise ValueError(f'no implicit tag for {provider!r}')
            tags = {tags}

        seen = fallback_default_dict(set)
        
        flush = self.flush
        registry = self.providers

        for scope in at:
            for s, seq in self._iter_abstracts(tags):
                at = s and scope_name(s, scope) or scope
                skip = seen[at]
                for tag in seq:
                    if not (tag in skip or skip.add(tag)):
                        if not isinstance(tag, Injectable):
                            raise TypeError(f'injector tag must be Injectable not {tag.__class__.__name__}: {tag}')

                        flush(tag, at)
                        registry[at].append(tag, provider)

    @classmethod
    def _iter_abstracts(cls, tags):
        if isinstance(tags, Set):
            yield None, tags
        elif isinstance(tags, dict):
            for k, v in tags.items():
                if isinstance(v, Set):
                    yield k, v
                else:
                    yield k, [v]
        else:
            yield None, [tags]

    @t.overload
    def alias(self, 
            tags: t.Union[_T_Tags, None], 
            use: T_UsingAlias, 
            *, 
            at: t.Union[_T_ScopeNames, None] = None, 
            priority: int = 1, 
            cache:bool=None, 
            **opts) -> _T_Tags:
        ...

    @t.overload
    def alias(self, 
            *, 
            use: T_UsingAlias, 
            at: t.Union[_T_ScopeNames, None] = None, 
            priority: int = 1, 
            cache:bool=None, 
            **opts) -> Callable[[_T_Tags], _T_Tags]:
        ...
    @t.overload
    def alias(self, 
            tags: t.Union[_T_Tags, None],
            *, 
            at: t.Union[_T_ScopeNames, None] = None, 
            priority: int = 1, 
            cache:bool=None, 
            **opts) -> Callable[[T_UsingAlias], T_UsingAlias]:
        ...

    def alias(self, tags: t.Union[_T_Tags, None]=..., use: T_UsingAlias=..., **kwds):
        """Registers an `AliasProvider`
        """
        def register(obj):
            if use is ...:
                tag, use_ = tags, obj
            else:
                tag, use_ = obj, use

            self.register(tag, use_, kind=KindOfProvider.alias, **kwds)
            return obj
    
        if tags is ... or use is ...:
            return register
        else:
            return register(tags)    


    @t.overload
    def value(self, 
            provide: _T_Tags, /,
            use: T_UsingValue, *, 
            at: t.Union[_T_ScopeNames, None] = None, 
            priority: int = 1, 
            cache:bool=None, 
            **opts) -> _T_Tags:
        ...
    @t.overload
    def value(self, 
            *, 
            use: T_UsingValue,
            at: t.Union[_T_ScopeNames, None] = None, 
            priority: int = 1, 
            cache:bool=None, 
            **opts) -> Callable[[_T_Tags], _T_Tags]:
        ...

    def value(self, provide:  t.Union[_T_Tags, None]=None, /, use: T_UsingValue=..., **kwds):
        """Registers an `AliasProvider`
        """
        def register(obj: _T_Tags):
            self.register(obj, use, kind=KindOfProvider.value, **kwds)

            return obj

        if provide is None:
            return register
        else:
            return register(provide)    

    @t.overload
    def function(self, 
            provide: t.Union[_T_Tags, None], /, 
            use: T_UsingFunc, *, 
            at: t.Union[_T_ScopeNames, None] = None, 
            priority: int = 1, 
            cache:bool=None, 
            **opts) -> _T_Tags:
        ...
    @t.overload
    def function(self, 
            *, 
            use: T_UsingFunc, 
            at: t.Union[_T_ScopeNames, None] = None, 
            priority: int = 1, 
            cache:bool=None, 
            **opts) -> Callable[[_T_Tags], _T_Tags]:
        ...

    @t.overload
    def function(self, 
            provide: t.Union[_T_Tags, None]=None, /, 
            *, 
            at: t.Union[_T_ScopeNames, None] = None, 
            priority: int = 1, 
            cache:bool=None, 
            **opts) -> Callable[[T_UsingFunc], T_UsingFunc]:
        ...

    def function(self, provide: t.Union[_T_Tags, None]=None, /, use: T_UsingFunc =..., **kwds):
        """Registers an `AliasProvider`
        """
        def register(obj):
            if use is ...:
                tag, use_ = provide, obj
            else:
                tag, use_ = obj, use

            self.register(tag, use_, kind=KindOfProvider.func, **kwds)
            return obj
    
        if provide is None or use is ...:
            return register
        else:
            return register(provide)    

    @t.overload
    def type(self, 
            provide: t.Union[_T_Tags, None], 
            /,
            use: T_UsingType, *, 
            at: t.Union[_T_ScopeNames, None] = None, 
            priority: int = 1, 
            cache:bool=None, 
            **opts) -> _T_Tags:
        ...

    @t.overload
    def type(self, *,
            use: T_UsingType, 
            at: t.Union[_T_ScopeNames, None] = None, 
            priority: int = 1, 
            cache:bool=None, 
            **opts) -> Callable[[_T_Tags], _T_Tags]:
        ...
    @t.overload
    def type(self, 
            provide: t.Union[_T_Tags, None]=None, 
            /, *, 
            at: t.Union[_T_ScopeNames, None] = None, 
            priority: int = 1, 
            cache:bool=None, 
            **opts) -> Callable[[T_UsingType], T_UsingType]:
        ...

    def type(self, provide: t.Union[_T_Tags, None]=None, /, use: T_UsingType =..., **kwds):
        def register(obj):
            if use is ...:
                tag, use_ = provide, obj
            else:
                tag, use_ = obj, use

            self.register(tag, use_, kind=KindOfProvider.type, **kwds)
            return obj
    
        if provide is None or use is ...:
            return register
        else:
            return register(provide)    
            
    @t.overload
    def injectable(self, 
                provide: t.Union[_T_Tags, None], /,
                use: T_UsingAny, 
                *,
                at: t.Union[_T_ScopeNames, None] = None,
                cache:bool=None, 
                kind: KindOfProvider,
                priority: int = 1,  
                **opts) -> _T_Tags:
        ...    
    @t.overload
    def injectable(self, 
                *,
                use: T_UsingAny, 
                at: t.Union[_T_ScopeNames, None] = None,
                cache:bool=None, 
                kind: KindOfProvider,
                priority: int = 1,  
                **opts) -> Callable[[_T_Tags], _T_Tags]:
        ...
    @t.overload
    def injectable(self, 
                provide: t.Union[_T_Tags, None]=None,
                 /, *,
                at: t.Union[_T_ScopeNames, None] = None,
                cache:bool=None, 
                kind: KindOfProvider,
                priority: int = 1,  
                **opts) -> Callable[[T_UsingAny], T_UsingAny]:
        ...

    def injectable(self, provide: t.Union[_T_Tags, None]=None, /, use: T_UsingAny =..., **kwds):
        def register(obj):
            if use is ...:
                tag, use_ = provide, obj
            else:
                tag, use_ = obj, use

            kind = kwds.pop('kind', None)
            if not kind:
                if not callable(use_):
                    raise TypeError(f'expected Callable but got {type(use_)} for {tag!r}')
                elif isinstance(use_, (type, GenericAlias)):
                    kind = KindOfProvider.type
                else:
                    kind = KindOfProvider.func

            self.register(tag, use_, kind=kind, **kwds)
            return obj
    
        if provide is None or use is ...:
            return register
        else:
            return register(provide)    

    @t.overload
    def provide(self, 
            tags: _T_Tags, 
            use: T_UsingFactory, 
            *, 
            at: t.Union[_T_ScopeNames, None] = None, 
            priority: int = 1, 
            cache:bool=None, 
            **opts) -> T_UsingFactory:
        ...
    @t.overload
    def provide(self, 
            tags: _T_Tags, 
            *, 
            at: t.Union[_T_ScopeNames, None] = None, 
            priority: int = 1, 
            cache:bool=None, 
            **opts) -> Callable[[T_UsingFactory], T_UsingFactory]:
        ...

    @t.overload
    def provide(self, *, 
            use: T_UsingFactory, 
            at: t.Union[_T_ScopeNames, None] = None, 
            priority: int = 1, 
            cache:bool=None, 
            **opts) -> Callable[[_T_Tags], _T_Tags]:
        ...

    def provide(self, tags: _T_Tags=..., use: T_UsingFactory =..., **kwds):
        def register(obj):
            if use is ...:
                tag, use_ = tags, obj
            else:
                tag, use_ = obj, use

            self.register(tag, use_, kind=KindOfProvider.factory, **kwds)
            return obj
    
        if tags is ... or use is ...:
            return register
        else:
            return register(tags)    

    @t.overload
    def resolver(self, 
            tags: _T_Tags, 
            use: T_UsingResolver, 
            *, 
            at: t.Union[_T_ScopeNames, None] = None, 
            priority: int = 1, 
            cache:bool=None, 
            **opts) -> T_UsingResolver:
        ...
    
    @t.overload
    def resolver(self, *, 
            use: T_UsingResolver, 
            at: t.Union[_T_ScopeNames, None] = None, 
            priority: int = 1, 
            cache:bool=None, 
            **opts) -> Callable[[_T_Tags], _T_Tags]:
        ...

    def resolver(self, tags: _T_Tags=..., use: T_UsingResolver =..., **kwds):
        def register(obj):
            if use is ...:
                tag, use_ = tags, obj
            else:
                tag, use_ = obj, use

            self.register(tag, use_, kind=KindOfProvider.resolver, **kwds)
            return obj
    
        if tags is ... or use is ...:
            return register
        else:
            return register(tags)    



def _default_make_container():
    return IocContainer('main')




@signals.setup.connect_via(IocContainer)
def _discover_scopes(sender, *, instance: IocContainer, **kwds):
    instance.discover_scopes(text.compact((os.environ.get(IOC_CONTAINER_ENV_KEY) or '').replace(',', ' ')).split(' '))




def _make_env_ioc():
    try:
        key = os.environ.get(IOC_CONTAINER_ENV_KEY, f'{__name__}:_default_make_container')
        ioc = ImportRef(key)(None)
        if not isinstance(ioc, IocContainer):
            if callable(ioc):
                ioc = ioc()

            if not isinstance(ioc, IocContainer):
                raise TypeError(
                    f'ENV_KEY {IOC_CONTAINER_ENV_KEY} must be a path to an IocContainer. '
                    f'{key!r} resolves to {type(ioc)}'
                )
        return ioc
    except Exception as e:
        logger.exception(e)
        raise e
    


ioc: IocContainer = proxy(_make_env_ioc, cache=True, callable=True)


if t.TYPE_CHECKING:
    def get_ioc_container():
        return ioc
else:
    get_ioc_container = ioc



export('ioc', 'get_ioc_container')