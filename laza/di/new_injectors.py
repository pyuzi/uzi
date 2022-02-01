from contextvars import ContextVar
import logging
import typing as t
from types import FunctionType, GenericAlias
from laza.common.collections import frozendict, nonedict
from laza.common.imports import ImportRef


from laza.common.functools import export

from laza.common.functools import Void

from .common import (
    Injectable,
    InjectorVar,
    T_Injectable,
    T_Injected,
)


from .exc import InjectorKeyError


if t.TYPE_CHECKING:
    from .new_scopes import AbcScope
    from .new_container import AbcIocContainer


export(Injectable)

logger = logging.getLogger(__name__)


_T = t.TypeVar("_T")
_T_Injector = t.TypeVar("_T_Injector", bound="Injector", covariant=True)


if t.TYPE_CHECKING:

    class InjectorContext(ContextVar):
        ...


InjectorContext = ContextVar[_T_Injector]


@export()
class InjectorVarDict(dict[T_Injectable, InjectorVar]):

    __slots__ = ("injector",)

    injector: "Injector"

    def __init__(self, injector: "Injector"):
        self.injector = injector

    def __missing__(self, key):
        inj = self.injector
        res = inj.scope.resolvers[key]
        if res is None:
            return self.setdefault(key, inj.parent.vars[key])
        return self.setdefault(key, res(inj))


@export()
class Injector(t.Generic[T_Injectable, T_Injected]):

    __slots__ = (
        "scope",
        "parent",
        "vars",
        "level",
        "_dispatched",
        "__weakref__",
    )

    _vars_class: t.ClassVar[type[InjectorVarDict]] = InjectorVarDict

    scope: "AbcScope"
    parent: "Injector"
    vars: dict[T_Injectable, InjectorVar]

    level: int

    def __init__(self, scope: "AbcScope", parent: "Injector" = None) -> None:
        self.scope = scope
        self.parent = NullInjector() if parent is None else parent
        self.level = 0 if parent is None else parent.level + 1
        self.vars = None
        self._dispatched = 0

    @property
    def root(self) -> "Injector":
        if self.level > 0:
            return self.parent.root
        else:
            return self

    @property
    def name(self) -> str:
        return self.scope.name

    def dispatch(self):
        self._dispatched += 1
        if self._dispatched == 1:
            self.scope.dispatch_injector(self)
            self.parent.dispatch()
            self._on_dispatch()
        return self

    def dispose(self):
        if self._dispatched == 1:
            self.scope.dispose_injector(self)
            self.parent.dispose()
            self._on_dispose()
        elif self._dispatched <= 0:
            raise RuntimeError(f"injector {self} already disposed.")
        self._dispatched -= 1
        return self

    def _on_dispatch(self):
        # ...
        self.vars = self._vars_class(self)

    def _on_dispose(self):
        # ...
        self.vars = None

    def get(
        self, injectable: T_Injectable, default: _T = None
    ) -> t.Union[T_Injected, _T]:
        try:
            return self[injectable]
        except InjectorKeyError:
            return default

    def __getitem__(self, key: T_Injectable) -> T_Injected:
        res = self.vars[key]
        if res is None:
            return self[self.__missing__(key)]
        elif res.value is Void:
            return res.get()
        return res.value

    def make(self, key: T_Injectable, /, *args, **kwds) -> T_Injected:
        res = self.vars[key]
        if res is None:
            key = self.__missing__(key)
            return self.make(key, *args, **kwds)
        elif args or kwds:
            # logger.warning(
            #     f'calling {self.__class__.__name__}.make() with args or kwds. {key} got {args=}, {kwds=}'
            # )
            return res.make(*args, **kwds)
        elif res.value is Void:
            return res.get()
        return res.value

    def __missing__(self, key):
        if isinstance(key, ImportRef):
            concrete = key(None)
            if concrete is not None:
                logger.warning(f"Cannot bind {key!r} Implicit binding is deprecated.")
                # self.ioc.alias(key, concrete, at=self.name, priority=-10)
                # return concrete
        elif isinstance(key, (type, FunctionType)):
            logger.warning(f"Cannot bind {key!r} Implicit binding is deprecated.")
            # self.ioc.injectable(key, use=key, at=self.name)
            # return key

        raise InjectorKeyError(f"{key} in {self!r}")

    def __contains__(self, x) -> bool:
        if self.vars is not None:
            if isinstance(x, Injector):
                x = x.scope
            return x in self.vars or x in self.parent
        return False

    def __bool__(self) -> bool:
        return True

    def __len__(self) -> bool:
        return len(self.vars)

    def __str__(self) -> str:
        return f"{self.__class__.__name__}[{self.level}]({self.name!r})"

    def __repr__(self) -> str:
        return f"<{self}, {self.parent!r}>"

    def __enter__(self: "Injector") -> "Injector":
        return self.dispatch()

    def __exit__(self, *exc):
        self.dispose()


class _NullInjectorVars(frozendict):
    __slots__ = ()

    def __missing__(self, k):
        if not isinstance(k, Injectable):
            raise TypeError(f"key must be Injectable, not {k.__class__.__name__}")


@export()
class NullInjector(Injector):
    """NullInjector Object"""

    __slots__ = ("name",)

    scope = None
    parent = None
    level = -1

    def __init__(self, name=None):
        _none_var = InjectorVar(None)
        self.vars = _NullInjectorVars({None: _none_var, type(None): _none_var})
        self.name = name or "null"

    def get(self, k: T_Injectable, default: _T = None) -> _T:
        return default

    def __contains__(self, x) -> bool:
        return False

    def __bool__(self):
        return False

    def __len__(self):
        return 0

    def __missing__(self, k: T_Injectable, args=None, kwds=None) -> None:
        raise InjectorKeyError(f"{k} in {self!r}")

    def dispatch(self):
        return self

    def dispose(self):
        return self
