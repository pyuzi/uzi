import logging
from types import GenericAlias
import typing as t


from functools import partial, update_wrapper
from contextvars import ContextVar
from collections.abc import Callable
from contextlib import AbstractContextManager, contextmanager
from cachetools.keys import hashkey


from djx.common.proxy import Proxy, unproxy
from djx.common.utils import export


from .injectors import Injector, NullInjector
from .scopes import Scope, MainScope
from .inspect import signature, ordered_id
from . import abc

from .container import ioc


from .abc import (
    ANY_SCOPE, LOCAL_SCOPE, MAIN_SCOPE, REQUEST_SCOPE, COMMAND_SCOPE,
    Injectable, InjectorKeyError, ScopeAlias, StaticIndentity, 
    T, T_Injected, T_Injector, T_Injectable
)

if not t.TYPE_CHECKING:
    __all__ = [
        'current',
        'ANY_SCOPE',
        'LOCAL_SCOPE', 
        'MAIN_SCOPE',
        'REQUEST_SCOPE', 
        'COMMAND_SCOPE',
    ]


logger = logging.getLogger(__name__)


_T_Callable = t.TypeVar('_T_Callable', type, Callable, covariant=True)

__real_main_inj = None

def __get_main_inj():
    global __real_main_inj

    rv = MainScope().create()
    __injector_ctxvar.set(rv)

    if __debug__:
        logger.debug(f'start: {rv!r}')

    return rv


__main_inj = Proxy(__get_main_inj, cache=True, callable=False)
__injector_ctxvar: t.Final = ContextVar[Injector]('__inj_ctxvar', default=__main_inj)


# current: Callable[[], Injector] = __injector_ctxvar.get
# injector: Injector = Proxy(current, callable=False)


@export()
def alias(*a, **kw):
    return ioc.alias(*a, **kw)


@export()
def injectable(*a, **kw):
    return ioc.injectable(*a, **kw)

@export()
def provide(*a, **kw):
    return ioc.provide(*a, **kw)

@export()
def value(*a, **kw):
    return ioc.value(*a, **kw)

@export()
def is_provided(*obj, **kw):
    return ioc.is_provided(*obj, **kw)


@export()
def current(obj):
    return ioc.current(obj)



@export()
def at(*a, **kw):
    return ioc.at(*a, **kw)

@export()
def get(*a, **kw):
    return ioc.get(*a, **kw)

@export()
def call(*a, **kw):
    return ioc.call(*a, **kw)

@export()
def proxy(*a, **kw):
    return ioc.proxy(*a, **kw)

@export()
def make(*a, **kw):
    return ioc.make(*a, **kw)

@export()
def wrap(*a, **kw):
    return ioc.wrap(*a, **kw)

@export()
def use(*a, **kw):
    return ioc.use(*a, **kw)


if t.TYPE_CHECKING:
    alias = ioc.alias
    injectable = ioc.injectable
    provide = ioc.provide
    value = ioc.value
    is_provided = ioc.is_provided

    at = ioc.at
    get = ioc.get
    call = ioc.call
    make = ioc.make
    proxy = ioc.proxy
    wrap = ioc.wrap
    use = ioc.use
    current = ioc.current






# @export()
# def at(*scopes: t.Union[str, ScopeAlias, type[Scope]], default=...):
#     """Get the first available Injector for given scope(s).
#     """
#     return current().at(*scopes, default=default)



# @export()
# def make(key, *args, **kwds):
#     return current().make(key, *args, **kwds)


# @export()
# def get(abstract: T_Injectable, default: T = None, /, *args, **kwds):
#     return current().get(abstract, default, *args, **kwds)



# @export()
# def scope(name: t.Union[str, ScopeAlias] = Scope.MAIN) -> T_Injector:
#     inj = current()()
#     scope = Scope[name]
#     if scope not in inj:
#         inj = scope().create(inj)
#         inj.context.wrap(use(inj))
#     return inj



# @export()
# @contextmanager
# def use(inj: t.Union[str, ScopeAlias, T_Injector] = Scope.MAIN) -> AbstractContextManager[T_Injector]:
#     cur: Injector[Scope] = current()()

#     scope = Scope[inj]
#     token = None
    
#     if scope not in cur:
#         if isinstance(inj, Injector):
#             if cur is not inj[cur.scope]:
#                 raise RuntimeError(f'{inj!r} must be a descendant of {cur!r}.')
#             cur = inj
#         else:
#             cur = scope().create(cur)
#         token = __injector_ctxvar.set(cur)
#         if __debug__:
#             logger.debug(f'set current: {cur!r}')

#     try:
#         yield current()
#     finally:
#         if __debug__ and token:
#             logger.debug(f'reset current: {token.old_value!r} {id(token.old_value)!r}')
#         token is None or __injector_ctxvar.reset(token)



# @t.overload
# def wrap(cls: type[T], /, *, scope: str=None, priority=-1, **kwds) -> type[T]:
#     ...
# @t.overload
# def wrap(func: Callable[..., T], /, *, scope: str=None, priority=-1, **kwds) -> Callable[..., T]:
#     ...
# @t.overload
# def wrap(*, scope: str=None, priority=-1, **kwds) -> Callable[[_T_Callable], _T_Callable]:
#     ...
# @export()
# def wrap(func: _T_Callable =..., /, *, scope: str=None, **kwds) -> _T_Callable:
    
#     scope = scope or ANY_SCOPE

#     def decorate(fn):
#         aka = _WrappedAlias(fn, (scope, ordered_id()))
#         provide(aka, scope=scope, factory=fn, **kwds)
#         return aka
    
#     if func is ...:
#         return decorate
#     else:
#         return decorate(func)






# @export()
# def wrapped(*args, **kwds):
#     def decorate(fn):
#         return wrap(fn, args, kwds)
#     return decorate




# @export()
# def call(func: Callable[..., T], /, *args: tuple, **kwargs) -> T:
#     # inj = __inj_ctxvar.get()
#     # params = signature(func).bind_partial(*args, **kwargs)
#     return current().make(func, *args, **kwargs)
#     # func(*params.inject_args(inj), **params.inject_kwargs(inj))





# class Dependency(t.NamedTuple):

#     depends: Injectable[T_Injected] = None
#     scope: str = Scope.ANY




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
        self.token = self.__class__, self.ioc.get_scope_name(scope, 'any'), dep,

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
        ioc.is_provided(token, scope) or ioc.alias(token, dep, scope=scope)

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



injected_property = export(InjectedProperty, name='injected_property')




@export()
class InjectedClassVar(InjectedProperty[T_Injected]):

    def __get__(self, obj, typ=...) -> T_Injected:
        return super().__get__(typ, typ)


if t.TYPE_CHECKING:
    InjectedClassVar = t.ClassVar[T_Injected]


injected_class_property = export(InjectedClassVar, name='injected_class_property')



# @abc.Injectable.register
# class _WrappedAlias(GenericAlias):

#     __slots__ = ()

#     # def __new__(cls, orig, *args, **kwds):
#     #     if cls is WrappedAlias:
#     #         if isinstance(orig, (type, GenericAlias)):
#     #             cls = WrappedTypeAlias
#     #         else:
#     #             cls = WrappedCallableAlias
        
#     #     return super().__new__(cls, orig, *args, **kwds)

#     def __call__(self, *args, **kwds):
#         return current().make(self, *args, **kwds)



# # class WrappedTypeAlias(WrappedAlias):

# #     __slots__ = ()


# class WrappedCallableAlias(WrappedAlias):

#     __slots__ = ()

