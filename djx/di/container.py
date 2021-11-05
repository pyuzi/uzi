from collections import defaultdict, deque
from contextlib import AbstractContextManager, contextmanager, nullcontext
from contextvars import ContextVar
from functools import partial, update_wrapper, wraps
from logging import getLogger
import os
from threading import RLock
from types import FunctionType, GenericAlias, MethodType, new_class
import typing as t

from collections.abc import Callable, Mapping, Set, Iterable, Hashable

from djx.common.collections import PriorityStack, fallback_default_dict, fallbackdict, frozendict, nonedict, orderedset
from djx.common.imports import ImportRef
from djx.common.proxy import proxy 
from djx.common.saferef import SafeRefSet
from djx.common.utils import export, text, Missing, noop

from . import abc, signals

from .abc import (
    Injectable, ScopeAlias, T_UsingFactory, T_UsingFunc, 
    T_Injectable, T_Injected, MAIN_SCOPE,
    T_UsingAny, T_UsingAlias, T_UsingResolver, T_UsingType, T_UsingValue,
)

from .common import KindOfProvider


if t.TYPE_CHECKING:
    from . import Scope as BaseScope, Provider, Injector
    from .providers import T_UsingAny
else:
    __all__ = [
        'IOC_SCOPES_ENV_KEY',
        'IOC_CONTAINER_ENV_KEY'
    ]

logger = getLogger(__name__)

IOC_CONTAINER_ENV_KEY = 'IOC_CONTAINER'
IOC_SCOPES_ENV_KEY = 'IOC_SCOPES'


_T = t.TypeVar('_T')
_T_Callable = t.TypeVar('_T_Callable', type, Callable, covariant=True)
_T_Tags = t.Union[T_Injectable, Set[T_Injectable], dict[str, t.Union[T_Injectable, Set[T_Injectable]]]]
_T_ScopeNames = t.Union[str, Set[str]]


@export()
class IocContainer:

    __slots__ = (
        'providers', '_lock', '_onboot', 'bootstrapped',
        'default_scope', 'Scope', 'scopes', 'scope_aliases', 
        '_main', 'ctxvar',
    )

    providers: fallback_default_dict[str, PriorityStack[abc.Injectable, 'Provider']]
    dep_class: type['Provider']

    _onboot: t.Union[deque[Callable[['IocContainer'], t.Any]], None]

    Scope:  type['BaseScope']
    scopes: fallbackdict[str, 'Scope']
    scope_aliases: fallbackdict[str, str]
    default_scope: str
    main: 'Injector' 
    root: 'Injector' 
    ctxvar: ContextVar['Injector']
    signals: t.ClassVar = signals


    def __init__(self, 
                default_scope: str=MAIN_SCOPE, *,
                base_scope: type['Scope']=None,
                scope_aliases: t.Union[Mapping, None]=None,
                ctxvar=None):
        from .scopes import Scope

        setattr = object.__setattr__
        setattr(self, '_lock', RLock())
        setattr(self, '_onboot', deque())
        setattr(self, 'bootstrapped', False)

        setattr(self, 'Scope', base_scope or Scope)

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
            
            self._run_onboot_callbacks(exhaust=True)

            self.signals.boot.send(self.__class__, instance=self)

            setattr(self, '_main', self._make_main_injector_())
            setattr(self, 'bootstrapped', True)

            self.signals.ready.send(self.__class__, instance=self)

    # def _populate_scopes_(self):
        # scopes = self.Scope._active_types()
        # for scope in scopes:
            # self.scopes[scope]

    # def _populate_providers_(self):
    #     pass

    def __setattr__(self, name, val):
        getattr(self, name)
        AttributeError(f'cannot set readonly attribute {name!r} on {self.__class__.__name__}')

    def proxy(self, tag: Injectable[T_Injected], *, default=..., callable: bool=None) -> T_Injected:
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

    def make(self, key, *args, **kwds):
        return self.injector.make(key, *args, **kwds)

    def get(self, tag: T_Injectable, default: _T = None, /, *args, **kwds):
        return self.injector.get(tag, default, *args, **kwds)

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
    
    def __getitem__(self, key):
        return self.injector.__getitem__(key)

    # def __setitem__(self, key, val):
    #     self.injector.__setitem__(key)

    def is_provided(self, obj, scope=None):
        if obj is not None:
            scope = self.scope_name(scope, None)
            for dct in ((self.providers[scope],) if scope else self.providers.values()):
                if obj in dct:
                    return True
        return False

    @classmethod
    def _unslice_key(cls, key):
        if key.__class__ is slice:
            return (None if key.start == 0 else key.start), key.stop, key.step or 1
        else:
            return None, key, 1

    def create_provider(self, provider: t.Union[abc.Provider, T_UsingAny] = Missing, **kwds: dict) -> 'Provider':
        if provider is Missing:
            ...
        elif isinstance(provider, abc.Provider):
            if kwds:
                kind = KindOfProvider(kwds.pop('kind', None) or provider.kind)
                if kind is not provider.kind:
                    raise TypeError(f'incompatible kinds {provider.kind} to {kind}')
                return provider.replace(**kwds)
        else:
            kwds['using'] = provider

        kind = KindOfProvider(kwds.pop('kind'))
        cls = self._get_provider_class(kind, kwds)
        return cls(**kwds)

    def _get_provider_class(self, kind: 'KindOfProvider', kwds: dict) -> type['Provider']:
        return kind.default_impl

    def flush(self, tag: T_Injectable, scope: str=None):
        scope = self.scope_name(scope)
        if scope := self.scopes.get(scope):
            scope.flush(tag)

    def _register_provider(self, 
                tags: t.Union[_T_Tags, None],
                using: t.Union[abc.Provider, T_UsingAny],
                at: t.Union[_T_ScopeNames, None] = None, 
                *, 
                flush: bool = True,
                **kwds) -> None:
        
        provider = self.create_provider(using, **kwds)

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
        
        for scope in at:
            for s, seq in self._iter_abstracts(tags):
                at = s and scope_name(s, scope) or scope
                skip = seen[at]
                for tag in seq:
                    if not (tag in skip or skip.add(tag)):
                        flush is False or self.flush(tag, at)
                        self.providers[at].append(tag, provider)

    def _iter_abstracts(self, tags):
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
    def register(self, 
            tags: t.Union[_T_Tags, None],
            using: t.Union[abc.Provider, T_UsingAny],
            at: t.Union[_T_ScopeNames, None] = None, 
            *, 
            flush: bool = True,
            **kwds) -> None:
                ...
    def register(self, *args,**kwds):
        self.on_boot(self._register_provider, *args, **kwds)

    @t.overload
    def alias(self, 
            tags: t.Union[_T_Tags, None], 
            use: T_UsingAlias, 
            *, 
            at: t.Union[_T_ScopeNames, None] = None, 
            priority: int = 1, 
            cache:bool=None, 
            flush: bool = True,
            **opts) -> _T_Tags:
        ...

    @t.overload
    def alias(self, 
            *, 
            use: T_UsingAlias, 
            at: t.Union[_T_ScopeNames, None] = None, 
            priority: int = 1, 
            cache:bool=None, 
            flush: bool = True,
            **opts) -> Callable[[_T_Tags], _T_Tags]:
        ...
    @t.overload
    def alias(self, 
            tags: t.Union[_T_Tags, None],
            *, 
            at: t.Union[_T_ScopeNames, None] = None, 
            priority: int = 1, 
            cache:bool=None, 
            flush: bool = True,
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
            tag: _T_Tags, 
            value: T_UsingValue, *, 
            at: t.Union[_T_ScopeNames, None] = None, 
            priority: int = 1, 
            cache:bool=None, 
            flush: bool = True,
            **opts) -> _T_Tags:
        ...
    @t.overload
    def value(self, 
            tag: None, 
            value: T_UsingValue,
            *, 
            at: t.Union[_T_ScopeNames, None] = None, 
            priority: int = 1, 
            cache:bool=None, 
            flush: bool = True,
            **opts) -> Callable[[_T_Tags], _T_Tags]:
        ...

    def value(self, tag:  t.Union[_T_Tags, None]=None, value: T_UsingValue=..., **kwds):
        """Registers an `AliasProvider`
        """
        def register(obj: _T_Tags):
            self.register(obj, value, kind=KindOfProvider.value, **kwds)

            return obj

        if tag is None:
            return register
        else:
            return register(tag)    

    @t.overload
    def function(self, 
            tag: t.Union[_T_Tags, None], 
            func: T_UsingFunc, *, 
            at: t.Union[_T_ScopeNames, None] = None, 
            priority: int = 1, 
            cache:bool=None, 
            flush: bool = True,
            **opts) -> T_UsingFunc:
        ...
    @t.overload
    def function(self, 
            tag: t.Union[_T_Tags, None]=None, 
            *, 
            at: t.Union[_T_ScopeNames, None] = None, 
            priority: int = 1, 
            cache:bool=None, 
            flush: bool = True,
            **opts) -> Callable[[T_UsingFunc], T_UsingFunc]:
        ...

    def function(self, tag: t.Union[_T_Tags, None]=None, func: T_UsingFunc =..., **kwds):
        """Registers an `AliasProvider`
        """

        def register(obj: T_UsingFunc):
            self.register(tag, obj, kind=KindOfProvider.func, **kwds)
            return obj

        if func is ...:
            return register
        else:
            return register(func)    

    @t.overload
    def type(self, 
            tag: t.Union[_T_Tags, None], 
            cls: T_UsingType, *, 
            at: t.Union[_T_ScopeNames, None] = None, 
            priority: int = 1, 
            cache:bool=None, 
            flush: bool = True,
            **opts) -> T_UsingType:
        ...
    @t.overload
    def type(self, 
            tag: t.Union[_T_Tags, None]=None, 
            *, 
            at: t.Union[_T_ScopeNames, None] = None, 
            priority: int = 1, 
            cache:bool=None, 
            flush: bool = True,
            **opts) -> Callable[[T_UsingType], T_UsingType]:
        ...

    def type(self, tag: t.Union[_T_Tags, None]=None, cls: T_UsingType =..., **kwds):
        
        def register(obj: T_UsingType):
            self.register(tag, obj, kind=KindOfProvider.type, **kwds)
            return obj

        if cls is ...:
            return register
        else:
            return register(cls)    

    @t.overload
    def injectable(self, 
                tag: t.Union[_T_Tags, None],
                using: T_UsingAny, 
                *,
                at: t.Union[_T_ScopeNames, None] = None,
                cache:bool=None, 
                kind: KindOfProvider,
                priority: int = 1,  
                flush: bool = True,
                **opts) -> T_UsingAny:
        ...
    @t.overload
    def injectable(self, 
                tag: t.Union[_T_Tags, None]=None,
                *,
                at: t.Union[_T_ScopeNames, None] = None,
                cache:bool=None, 
                kind: KindOfProvider,
                priority: int = 1,  
                flush: bool = True,
                **opts) -> Callable[[T_UsingAny], T_UsingAny]:
        ...

    def injectable(self, tag: t.Union[_T_Tags, None]=None, using: T_UsingAny =..., **kwds):
        def register(obj: T_UsingAny):
            kind = kwds.pop('kind', None)
            if not kind:
                if not callable(obj):
                    raise TypeError(f'expected Callable but got {type(obj)} for {tag!r}')
                elif isinstance(obj, (type, GenericAlias)):
                    kind = KindOfProvider.type
                else:
                    kind = KindOfProvider.func
        
            self.register(tag, obj, kind=kind, **kwds)
            return obj

        return register if using is ... else register(using)

    @t.overload
    def provide(self, 
            tags: _T_Tags, 
            use: T_UsingFactory, 
            *, 
            at: t.Union[_T_ScopeNames, None] = None, 
            priority: int = 1, 
            cache:bool=None, 
            flush: bool = True,
            **opts) -> T_UsingFactory:
        ...
    @t.overload
    def provide(self, 
            tags: _T_Tags, 
            *, 
            at: t.Union[_T_ScopeNames, None] = None, 
            priority: int = 1, 
            cache:bool=None, 
            flush: bool = True,
            **opts) -> Callable[[T_UsingFactory], T_UsingFactory]:
        ...

    @t.overload
    def provide(self, *, 
            use: T_UsingFactory, 
            at: t.Union[_T_ScopeNames, None] = None, 
            priority: int = 1, 
            cache:bool=None, 
            flush: bool = True,
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
            flush: bool = True,
            **opts) -> T_UsingResolver:
        ...
    
    @t.overload
    def resolver(self, *, 
            use: T_UsingResolver, 
            at: t.Union[_T_ScopeNames, None] = None, 
            priority: int = 1, 
            cache:bool=None, 
            flush: bool = True,
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

    from .injectors import Injector
    from .resolvers import InjectorResolver

    instance.resolver(abc.Injector, InjectorResolver(), at='any', priority=-10)

    instance.alias(Injector, abc.Injector, at='any', priority=-10)

    


# @signals.setup.connect_via(IocContainer)
# def _discover_scopes(sender, *, instance: IocContainer, **kwds):
#     instance.discover_scopes(text.compact((os.environ.get(IOC_CONTAINER_ENV_KEY) or '').replace(',', ' ')).split(' '))



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
    


ioc: IocContainer = export(proxy(_make_env_ioc, cache=True), name='ioc')
