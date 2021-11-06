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

