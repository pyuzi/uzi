import asyncio
from inspect import isawaitable
import logging
import typing as t
from collections.abc import Callable
from contextlib import AsyncExitStack
from contextvars import ContextVar, Token
from threading import Lock
from types import MethodType

import attr

from xdi._common.functools import Missing, export
from typing_extensions import Self

from . import Dependency, Injectable, T_Default, T_Injectable, T_Injected
from .util import AsyncExitStack

if t.TYPE_CHECKING:
    from .scopes import BindingsMap, Scope
    from .scopes import Scope


logger = logging.getLogger(__name__)

_T = t.TypeVar('_T')


TContextBinding = Callable[
    ["InjectorContext", t.Optional[Injectable]], Callable[..., T_Injected]
]


class InjectorLookupError(LookupError):

    key: Injectable
    injector: "Injector"

    def __init__(self, key=None, injector: "Injector" = None) -> None:
        self.key = key
        self.injector = injector

    def __str__(self) -> str:
        key, injector = self.key, self.injector
        return (
            ""
            if key is None is injector
            else f"{key!r}"
            if injector is None
            else f"at {injector!r}"
            if key is None
            else f"{key!r} at {injector!r}"
        )


@attr.s(slots=True, cmp=False)
class Injector(dict[T_Injectable, Callable[[], T_Injected]]):

    # __slots__ = (
    #     "scope",
    #     "__parent",
    #     "__exitstack",
    #     "__bindings",
    # )

    parent: Self = attr.field()
    scope: "Scope" = attr.field()
    # __parent: Self
    # __bindings: dict[
    #     Injectable, Callable[[Self], Callable[[], Callable[[], T_Injected]]]
    # ]

    is_async: bool = attr.field(default=False, kw_only=True)
    exitstack: AsyncExitStack = attr.field(init=False)

    _exitstack_class: t.ClassVar[type[AsyncExitStack]] = AsyncExitStack

    # def __init__(
    #     self, parent: "InjectorContext", scope: "Scope", bindings: "BindingsMap"=None
    # ):
    #     self.__parent = parent
    #     self.scope = scope
    #     # self.__bindings = bindings
    #     self.__exitstack = self._exitstack_class()

    def __attrs_post_init__(self):
        self.exitstack = self._exitstack_class()

    @property
    def name(self) -> str:
        return self.scope.name

    # @property
    # def exitstack(self):
    #     return self.exitstack

    # @property
    # def base(self) -> str:
    #     return self

    # @property
    # def injector(self):
    #     return self.scope

    # @property
    # def parent(self):
    #     return self.__parent

    @t.overload
    def find(
        self, dep: T_Injectable, *fallbacks: T_Injectable
    ) -> Callable[[], T_Injected]:
        ...

    @t.overload
    def find(
        self, dep: T_Injectable, *fallbacks: T_Injectable, default: T_Default
    ) -> t.Union[Callable[[], T_Injected], T_Default]:
        ...

    def find(self, *keys, default=Missing):
        for key in keys:
            rv = self[key]
            if rv is None:
                continue
            return rv

        if default is Missing:
            raise InjectorLookupError(key, self)

        return default

    def make(
        self, key: T_Injectable, *fallbacks: T_Injectable, default=Missing
    ) -> T_Injected:
        if fallbacks:
            func = self.find(key, *fallbacks, default=None)
        else:
            func = self[key]

        if not func is None:
            return func()
        elif default is Missing:
            raise InjectorLookupError(key, self)
        return default

    def call(self, func: Callable[..., T_Injected], *args, **kwds) -> T_Injected:
        if isinstance(func, MethodType):
            args = (func.__self__,) + args
            func = func.__func__

        return self.make(func)(*args, **kwds)

    def __bool__(self):
        return True
        
    def __contains__(self, x) -> bool:
        return dict.__contains__(self, x) or x in self.parent

    def __missing__(self, key):
        # scope = self.scope
        # if isinstance(key, Dep):
        #     if bound := scope[key]:
        #         return _dict_setdefault(self, key, bound(self))
        #     elif key.loc is Dep.GLOBAL:
        #         return _dict_setdefault(self, key, self.parent[key])
        #     elif key.loc is Dep.SUPER:
        #         return _dict_setdefault(self, key, self.parent[key.replace(loc=)])
        #     if key.is_pure:
        #         return self[key.replace(scope=scope)]
        #     elif key.loc is Dep.SUPER:
        #         pass
        # else:
        #     return self[Dep(key, scope)]

        res = self.scope[key]
        if res is None:
            return self.__setdefault(key, self.parent[key])
        return self.__setdefault(key, res(self) or self.parent[key])

    __setdefault = dict.setdefault

    def __str__(self) -> str:
        return f"{self.__class__.__name__}({self.name!r})"

    def __repr__(self) -> str:
        return f"<{self!s}, {self.parent!r}>"

    def __eq__(self, x):
        return x is self

    def __ne__(self, x):
        return not self.__eq__(x)

    def __hash__(self):
        return id(self)

    def not_mutable(self, *a, **kw):
        raise TypeError(f"immutable type: {self} ")

    __delitem__ = (
        __setitem__
    ) = (
        setdefault
    ) = (
        pop
    ) = (
        popitem
    ) = update = clear = copy = __copy__ = __reduce__ = __deepcopy__ = not_mutable
    del not_mutable




class NullInjectorContext(Injector):
    """NullInjector Object"""

    __slots__ = ()

    name: t.Final = None
    injector = parent = None

    def noop(slef, *a, **kw):
        ...

    __init__ = __getitem__ = __missing__ = __contains__ = _reset = noop
    del noop

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}()'