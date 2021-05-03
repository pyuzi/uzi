import logging

from threading import Lock

from functools import update_wrapper
from contextvars import ContextVar
from collections.abc import Callable
from contextlib import AbstractContextManager, contextmanager
from typing import Literal, Union


from flex.utils.proxy import CachedProxy, Proxy
from flex.utils.decorators import export


from .injectors import Injector, NullInjector
from .scopes import Scope, MainScope
from .inspect import signature
from .providers import alias, provide, injectable
from . import abc
from .abc import ScopeAlias, T, T_Injected, T_Injector, T_Injectable

__all__ = [
    'head',
    'injector',
]

logger = logging.getLogger(__name__)




__null_inj = NullInjector()

__main_inj = CachedProxy(lambda:  MainScope().create())
__inj_ctxvar = ContextVar[T_Injector]('__inj_ctxvar', default=__main_inj)



head: Callable[[], T_Injector] = __inj_ctxvar.get
injector = Proxy(head)



@export()
def final():
    return head().final


@export()
def get(key: T_Injectable, default: T = None):
    return head().get(key, default)



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











