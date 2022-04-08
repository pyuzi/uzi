import typing as t
from abc import ABCMeta, abstractmethod
from enum import Enum, IntEnum, auto
from logging import getLogger
from pickle import GLOBAL
from types import FunctionType, GenericAlias, MethodType

import attr
from typing_extensions import Self

from ._common import Missing, calling_frame
from ._common.datapath import DataPath

if t.TYPE_CHECKING:
    from .providers import Provider
    from .scopes import Scope

    ProviderType = type[Provider]


T_Injected = t.TypeVar("T_Injected", covariant=True)
T_Default = t.TypeVar("T_Default")
T_Injectable = t.TypeVar("T_Injectable", bound="Injectable", covariant=True)


_logger = getLogger(__name__)


def is_injectable(obj):
    return isinstance(obj, Injectable)


def is_injectable_annotation(obj):
    """Returns `True` if the given type is injectable."""
    return is_injectable(obj)


class _PrivateABCMeta(ABCMeta):
    def register(self, subclass):
        if not (calling_frame().get("__package__") or "").startswith(__package__):
            raise TypeError(f"virtual subclasses not allowed for {self.__name__}")

        return super().register(subclass)


class Injectable(metaclass=_PrivateABCMeta):

    __slots__ = ()

    __class_getitem__ = classmethod(GenericAlias)

    def __init_subclass__(cls, *args, **kwargs):
        raise TypeError(f"Cannot subclass {cls.__name__}")


Injectable.register(type)
Injectable.register(t.TypeVar)
Injectable.register(FunctionType)
Injectable.register(MethodType)
Injectable.register(GenericAlias)
Injectable.register(type(t.Generic[T_Injected]))
Injectable.register(type(t.Union))


@Injectable.register
class InjectionMarker(t.Generic[T_Injectable], metaclass=_PrivateABCMeta):

    __slots__ = ()

    @property
    def __origin__(self):
        return self.__class__

    @property
    @abstractmethod
    def __dependency__(self) -> T_Injectable:
        ...


class DependencyLocation(IntEnum):

    GLOBAL: "DependencyLocation" = 0
    """start resolving from the current/given scope and it's parent.
    """

    NONLOCAL: "DependencyLocation" = auto()
    """Skip the current/given container and resolve from it's peers or parent instead.
    """

    LOCAL: "DependencyLocation" = auto()
    """Only inject from the current/given container without considering it's peers and parent
    """

    @classmethod
    def coerce(cls, val):
        return cls(val or 0)


@attr.s(slots=True, frozen=True, cmp=True, cache_hash=True)
class Dependency(t.Generic[T_Injectable]):

    """Marks an injectable as a `dependency` to be injected."""

    provides: T_Injectable = attr.field()
    scope: "Scope" = attr.field()
    provider: "Provider" = attr.field(repr=lambda p: str(p and id(p)))

    def __init_subclass__(cls, *args, **kwargs):
        raise TypeError(f"Cannot subclass {cls.__module__}.{cls.__qualname__}")

    def __call__(self, scope: "Scope"):
        if provider := scope is self.scope and self.provider:
            return provider.bind(scope, self.provides)


class DepInjectorFlag(Enum):

    # none: 'InjectFlag'      = None

    only_self: "DepInjectorFlag" = "ONLY_SELF"
    """Only inject from the current context without considering parents
    """

    skip_self: "DepInjectorFlag" = "SKIP_SELF"
    """Skip the current context and resolve from it's parent instead.
    """


@InjectionMarker.register
class Dep(DataPath[T_Injected]):

    """Marks an injectable as a `dependency` to be injected."""

    __slots__ = (
        "__injects__",
        "__injector__",
        "__v_hashident__",
        "__default__",
    )

    Flag = DepInjectorFlag

    ONLY_SELF: t.Final = DepInjectorFlag.only_self
    """Only inject from the current context without considering parents
    """

    SKIP_SELF: t.Final = DepInjectorFlag.skip_self
    """Skip the current context and resolve from it's parent instead.
    """

    _default_metadata = None, Missing, ()

    def __init_subclass__(cls, *args, **kwargs):
        raise TypeError(f"Cannot subclass {cls.__module__}.{cls.__name__}")

    @t.overload
    def __new__(
        cls: type[Self],
        dependency: T_Injectable,
        *,
        injector: t.Union[DepInjectorFlag, "Injector", None] = None,
        default=Missing,
    ) -> Self:
        ...

    def __new__(
        cls,
        dependency: T_Injectable,
        injector: t.Union[DepInjectorFlag, "Injector", None] = None,
        default=Missing,
        __expr=(),
    ):
        self = super().__new__(cls, __expr)
        object.__setattr__(self, "__injects__", dependency)
        object.__setattr__(self, "__injector__", injector)
        object.__setattr__(self, "__default__", default)
        return self

    @property
    def __origin__(self):
        return self.__class__

    @property
    def __metadata__(self):
        return self.__injector__, self.__default__, self.__expr__

    @property
    def __dependency__(self):
        return self.__injects__ if self.__hashident__ is None else self

    @property
    def __hasdefault__(self):
        return not self.__default__ is Missing

    @property
    def __hashident__(self) -> int:
        try:
            return self.__v_hashident__
        except AttributeError:
            meta = self.__metadata__
            ash = None
            if meta == self._default_metadata:
                object.__setattr__(self, "__v_hashident__", None)
            else:
                object.__setattr__(
                    self, "__v_hashident__", ash := hash((self.__injects__, meta))
                )
            return ash

    def __push__(self, *expr):
        return self.__class__(
            self.__injects__, self.__injector__, self.__default__, self.__expr__ + expr
        )

    def __reduce__(self):
        return self.__class__, (
            self.__injects__,
            self.__injector__,
            self.__default__,
            self.__expr__,
        )

    def __eq__(self, x) -> bool:
        if not isinstance(x, self.__class__):
            return self.__hashident__ is None and x == self.__injects__
        return self.__injects__ == x.__injects__ and self.__metadata__ == x.__metadata__

    def __hash__(self):
        ash = self.__hashident__
        if ash is None:
            return hash(self.__injects__)
        else:
            return ash

    def __str__(self):
        return f"{self.__injects__!s}" + "".join(map(str, self.__expr__))

    def __repr__(self) -> bool:
        dependency = self.__injects__
        injector = self.__injector__
        default = self.__default__
        return f'{self.__class__.__name__}({dependency=}, {default=}, {injector=}){"".join(map(str, self.__expr__))}'

    def __setattr__(self, name: str, value) -> None:
        getattr(self, name)
        raise AttributeError(f"cannot set readonly attribute {name!r}")


from .containers import Container
from .providers import Provider
from .scopes import Scope
