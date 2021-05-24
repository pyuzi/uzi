import logging

from threading import Lock

from functools import update_wrapper
from contextvars import ContextVar
from collections.abc import Callable
from contextlib import AbstractContextManager, contextmanager
from types import GenericAlias
from typing import ClassVar, Generic, Literal, NamedTuple, TYPE_CHECKING, Union, get_type_hints


from djx.common.proxy import Proxy
from flex.utils.decorators import export


from .injectors import Injector, NullInjector
from .scopes import Scope, MainScope
from .inspect import signature
from .providers import alias, is_provided, provide, injectable
from . import abc

from .abc import ANY_SCOPE, Injectable, InjectorKeyError, LOCAL_SCOPE, MAIN_SCOPE, ScopeAlias, StaticIndentity, T, T_Injected, T_Injector, T_Injectable

if not TYPE_CHECKING:
    __all__ = [
        'head',
        'injector',
        'ANY_SCOPE',
        'LOCAL_SCOPE', 
        'MAIN_SCOPE'
    ]


logger = logging.getLogger(__name__)


__null_inj = NullInjector()

__main_inj = Proxy(lambda:  MainScope().create(), cache=True, callable=True)
__inj_ctxvar = ContextVar[T_Injector]('__inj_ctxvar', default=__main_inj)



head: Callable[[], T_Injector] = __inj_ctxvar.get
injector = Proxy(head, callable=True)



@export()
def proxy(abstract: T_Injectable, *, callable: bool=None) -> Proxy[T_Injected]:
    def resolve():
        return head()[abstract]
    return Proxy(resolve, callable=callable)





@export()
def final():
    return head().final


@export()
def get(abstract: T_Injectable, default: T = None):
    return head().get(abstract, default)



@export()
@contextmanager
def scope(name: Union[str, ScopeAlias] = Scope.MAIN) -> AbstractContextManager[T_Injector]:
    cur = head()

    scope = Scope[name]
    token = None
    
    if scope not in cur:
        cur = scope().create(cur)
        token = __inj_ctxvar.set(cur)

    try:
        yield cur
    finally:
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





class Dependency(NamedTuple):
    depends: Injectable = None
    scope: str = Scope.ANY




@export()
class InjectedProperty(Generic[T_Injected]):
    
    __slots__ = '_dep','__name__', '_default', '__weakref__'

    _dep: Dependency
    __name__: str

    def __init__(self, dep: Injectable=None, default: T_Injected=..., *, name=None, scope=None) -> T_Injected:
        self._default = default
        self._dep = Dependency(dep, *(scope and (str(scope),) or ()))
        self.__name__ = name

    @property
    def depends(self):
        return self._dep.depends

    @property
    def scope(self):
        return self._dep.scope

    def __set_name__(self, owner, name):
        self.__name__ = name
        if self.depends is None:
            dep = get_type_hints(owner).get(name)
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
            return head()[self._dep]
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


if TYPE_CHECKING:
    InjectedClassVar = ClassVar[T_Injected]