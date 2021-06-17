import logging
import typing as t


from functools import update_wrapper
from contextvars import ContextVar
from collections.abc import Callable
from contextlib import AbstractContextManager, contextmanager


from djx.common.proxy import Proxy
from djx.common.utils import export


from .injectors import Injector, NullInjector
from .scopes import Scope, MainScope
from .inspect import signature
from .providers import alias, is_provided, provide, injectable
from . import abc

from .abc import (
    ANY_SCOPE, LOCAL_SCOPE, MAIN_SCOPE, REQUEST_SCOPE, COMMAND_SCOPE,
    Injectable, InjectorKeyError, ScopeAlias, StaticIndentity, 
    T, T_Injected, T_Injector, T_Injectable
)

if not t.TYPE_CHECKING:
    __all__ = [
        'current',
        'injector',
        'ANY_SCOPE',
        'LOCAL_SCOPE', 
        'MAIN_SCOPE',
        'REQUEST_SCOPE', 
        'COMMAND_SCOPE',
    ]


logger = logging.getLogger(__name__)



__real_main_inj = None

def __get_main_inj():
    global __real_main_inj

    rv = MainScope().create()
    __inj_ctxvar.set(rv)

    if __debug__:
        logger.debug(f'start: {rv!r}')

    return rv


__main_inj = Proxy(__get_main_inj, cache=True, callable=False)
__inj_ctxvar: t.Final = ContextVar[Injector]('__inj_ctxvar', default=__main_inj)


current: Callable[[], Injector] = __inj_ctxvar.get
injector = Proxy(current, callable=False)



@export()
def proxy(abstract: T_Injectable, *, callable: bool=None) -> T_Injectable: # -> Proxy[T_Injected]:
    def resolve():
        return current()[abstract]
    
    return Proxy(resolve, callable=callable)





@export()
def make(key, *args, **kwds):
    return current().make(key, *args, **kwds)


@export()
def get(abstract: T_Injectable, default: T = None):
    return current().get(abstract, default)



@export()
def scope(name: t.Union[str, ScopeAlias] = Scope.MAIN) -> T_Injector:
    inj = current()()
    scope = Scope[name]
    if scope not in inj:
        inj = scope().create(inj)
        inj.context.wrap(using(inj))
    return inj



@export()
@contextmanager
def using(inj: t.Union[str, ScopeAlias, T_Injector] = Scope.MAIN) -> AbstractContextManager[T_Injector]:
    cur: Injector[Scope] = current()()

    scope = Scope[inj]
    token = None
    
    if scope not in cur:
        if isinstance(inj, Injector):
            if cur is not inj[cur.scope]:
                raise RuntimeError(f'{inj!r} must be a descendant of {cur!r}.')
            cur = inj
        else:
            cur = scope().create(cur)
        token = __inj_ctxvar.set(cur)
        if __debug__:
            logger.debug(f'set current: {cur!r}')

    try:
        yield current()
    finally:
        if __debug__ and token:
            logger.debug(f'reset current: {token.old_value!r} {id(token.old_value)!r}')
        token is None or __inj_ctxvar.reset(token)




@export()
def wrapped(func: Callable[..., T], /, args: tuple=(), keywords:dict={}) -> Callable[..., T]:
    params = signature(func).bind_partial(*args, **keywords)
    def wrapper(inj: Injector=None, /, *args, **kwds) -> T:
        if inj is None: 
            inj = __inj_ctxvar.get()
        # fallbackdict(params.arguments, kwds)
        return func(*params.inject_args(inj), **params.inject_kwargs(inj))
    
    update_wrapper(wrapper, func)

    return wrapper if params else func





@export()
def wrap(*args, **kwds):
    def decorate(fn):
        return wrapped(fn, args, kwds)
    return decorate




@export()
def call(func: Callable[..., T], /, args: tuple=(), keywords:dict={}) -> T:
    inj = __inj_ctxvar.get()
    params = signature(func).bind_partial(*args, **keywords)
    return func(*params.inject_args(inj), **params.inject_kwargs(inj))





class Dependency(t.NamedTuple):
    depends: Injectable = None
    scope: str = Scope.ANY




@export()
class InjectedProperty(t.Generic[T_Injected]):
    
    __slots__ = '_dep','__name__', '_default', '__weakref__'

    _dep: Dependency
    __name__: str

    def __init__(self, dep: Injectable=None, default: T_Injected=..., *, name=None, scope=None) -> T_Injected:
        self._default = default
        self._dep = Dependency(dep, *(scope and (str(scope),) or ()))
        self.__name__ = name
        self._register()

    @property
    def depends(self):
        return self._dep.depends

    @property
    def scope(self):
        return self._dep.scope

    def __set_name__(self, owner, name):
        self.__name__ = name
        if self.depends is None:
            dep = t.get_type_hints(owner).get(name)
            if dep is None:
                raise TypeError(
                    f'Injectable not set for {owner.__class__.__name__}.{name}'
                )
            self._dep = self._dep._replace(depends=dep)
        self._register()

    def _register(self):   
        dep = self._dep
        if not (dep.depends is None or is_provided(dep)):
            alias(dep, dep.depends, scope=dep.scope)

    def __get__(self, obj, typ=None) -> T_Injected:
        if obj is None:
            return self
        try:
            return current()[self._dep]
        except InjectorKeyError as e:
            if self._default is ...:
                raise AttributeError(self) from e
            return self._default

    def __str__(self) -> T_Injected:
        return f'{self.__class__.__name__}({self._dep!r})'

    def __repr__(self) -> T_Injected:
        return f'<{self.__name__} = {self}>'






@export()
class InjectedClassVar(InjectedProperty[T_Injected]):

    def __get__(self, obj, typ=...) -> T_Injected:
        return super().__get__(typ, typ)


if t.TYPE_CHECKING:
    InjectedClassVar = t.ClassVar[T_Injected]