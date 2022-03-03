import typing as t
from abc import ABCMeta, abstractmethod
from logging import getLogger
from types import FunctionType, GenericAlias

from laza.common.datapath import DataPath
from laza.common.collections import frozendict
from laza.common.enum import Enum
from laza.common.functools import Missing, calling_frame, export
from typing_extensions import Self

if t.TYPE_CHECKING:
    from .injectors import Injector
    from .providers import Provider

    ProviderType = type[Provider]


T_Injected = t.TypeVar("T_Injected", covariant=True)
T_Default = t.TypeVar("T_Default")
T_Injectable = t.TypeVar("T_Injectable", bound="Injectable", covariant=True)

# export('T_Injected', 'T_Injectable', 'T_Default')

_logger = getLogger(__name__)


@export()
def isinjectable(obj):
    return isinstance(obj, Injectable)


class _PrivateABCMeta(ABCMeta):
    def register(self, subclass):
        if not (calling_frame().get("__package__") or "").startswith(__package__):
            raise TypeError(f"virtual subclasses not allowed for {self.__name__}")

        return super().register(subclass)


@export()
class Injectable(metaclass=_PrivateABCMeta):

    __slots__ = ()

    __class_getitem__ = classmethod(GenericAlias)

    def __init_subclass__(cls, *args, **kwargs):
        raise TypeError(f"Cannot subclass {cls.__name__}")


Injectable.register(type)
Injectable.register(t.TypeVar)
Injectable.register(FunctionType)
Injectable.register(GenericAlias)
Injectable.register(type(t.Generic[T_Injected]))
Injectable.register(type(t.Union))


@export()
@Injectable.register
class InjectionMarker(t.Generic[T_Injectable], metaclass=_PrivateABCMeta):

    __slots__ = (
        "__injects__",
        "__metadata__",
        "_hash",
    )

    __injects__: T_Injectable
    __metadata__: frozendict

    @property
    @abstractmethod
    def __dependency__(self) -> T_Injectable:
        ...

    def __new__(cls: type[Self], inject: T_Injectable, metadata: dict = (), /):
        if not isinjectable(inject):
            raise TypeError(
                f"`dependency` must be an Injectable not "
                f"`{inject.__class__.__name__}`"
            )

        self = object.__new__(cls)
        self.__injects__ = inject
        self.__metadata__ = frozendict(metadata)
        return self

    _create = classmethod(__new__)

    @property
    def __origin__(self):
        return self.__class__

    def _clone(self, metadata: dict = (), /, **extra_metadata):
        metadata = frozendict(metadata or self.__metadata__, **extra_metadata)
        return self._create(self.__injects__, metadata)

    def __getitem__(self: Self, type_: type[T_Injected]):
        """Annotate given type with this marker.

        Calling `marker[T]` is the same as `Annotated[type_, marker]`
        """
        if type_.__class__ is tuple:
            type_ = t.Annotated[type_]  # type: ignore

        return t.Annotated[type_, self]

    def __reduce__(self):
        return self._create, (self.__injects__, self.__metadata__)

    def __eq__(self, x) -> bool:
        if not isinstance(x, self.__class__):
            return not self.__metadata__ and x == self.__injects__
        return self.__injects__ == x.__injects__ and self.__metadata__ == x.__metadata__

    def __hash__(self):
        try:
            return self._hash
        except AttributeError:
            if self.__metadata__:
                self._hash = hash((self.__injects__, self.__metadata__))
            else:
                self._hash = hash(self.__injects__)
            return self._hash

    def __setattr__(self, name: str, value) -> None:
        if hasattr(self, "_hash"):
            getattr(self, name)
            raise AttributeError(f"cannot set readonly attribute {name!r}")

        return super().__setattr__(name, value)



class DepInjectorFlag(Enum):

    # none: 'InjectFlag'      = None

    only_self: "DepInjectorFlag" = "ONLY_SELF"
    """Only inject from the current context without considering parents
    """

    skip_self: "DepInjectorFlag" = "SKIP_SELF"
    """Skip the current context and resolve from it's parent instead.
    """


@export()
@InjectionMarker.register
class Dep(DataPath[T_Injected]):

    """Marks an injectable as a `dependency` to be injected."""

    __slots__ = (
        "__injects__",
        "__injector__",
        "__v_hashident__",
        "__default__",
    )

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

















from .ctx import context
from .injectors import Injector, inject
from .containers import Container