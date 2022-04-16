from collections import namedtuple
import operator
import typing as t
from abc import ABCMeta, abstractmethod
from enum import Enum, IntEnum
from logging import getLogger
from types import FunctionType, GenericAlias, MethodType

from typing_extensions import Self

import attr

from ._common import Missing, calling_frame, private_setattr
from ._common.lazy import LazyOp as BaseLazyOp

if t.TYPE_CHECKING:
    from .providers import Provider

    ProviderType = type[Provider]


T_Injected = t.TypeVar("T_Injected", covariant=True)
T_Default = t.TypeVar("T_Default")
T_Injectable = t.TypeVar("T_Injectable", bound="Injectable", covariant=True)


_logger = getLogger(__name__)

_NoneType = type(None)



_BLACKLIST = frozenset({
    None, 
    _NoneType,
    type(t.Literal[1]),
})


def is_injectable(obj):
    return isinstance(obj, Injectable) \
        and not (obj in _BLACKLIST or isinstance(obj, NonInjectable))


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



class NonInjectable(metaclass=_PrivateABCMeta):
    __slots__ = ()
    def __init_subclass__(cls, *args, **kwargs):
        raise TypeError(f"Cannot subclass {cls.__name__}")


NonInjectable.register(_NoneType)
NonInjectable.register(type(t.Literal[1]))




@Injectable.register
class InjectionMarker(t.Generic[T_Injectable], metaclass=_PrivateABCMeta):

    __slots__ = ()

    @property
    def __origin__(self):
        return self.__class__

    @property
    # @abstractmethod
    def __dependency__(self) -> T_Injectable:
        ...



class DepScope(IntEnum):

    any: 'DepScope'       = 0
    """Inject from any scope.
    """

    only_self: "DepScope" = 1
    """Only inject from the current scope without considering parents
    """

    skip_self: "DepScope" = 2
    """Skip the current scope and resolve from it's parent instead.
    """

_object_new = object.__new__




@InjectionMarker.register
@private_setattr
class PureDep(t.Generic[T_Injectable]):
    __slots__ = 'abstract',

    abstract: T_Injected

    scope: t.Final = DepScope.any
    default: t.Final = Missing
    has_default: t.Final = False
    injects_default: t.Final = False

    def __new__(cls: type[Self], abstract: T_Injectable) -> Self:
        self = _object_new(cls)
        self.__setattr(abstract=abstract)
        return self

    def forward_op(op):
        def method(self: Self, *a):
            return op(self.abstract, *a)
        return method
    
    # @property
    # def __dependency__(self):
    #     return self.abstract

    __eq__ = forward_op(operator.eq)
    __ne__ = forward_op(operator.ne)
    
    __gt__ = forward_op(operator.gt)
    __ge__ = forward_op(operator.ge)

    __lt__ = forward_op(operator.lt)
    __le__ = forward_op(operator.le)

    __hash__ = forward_op(hash)
    __bool__ = forward_op(bool)

    del forward_op
    
    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.abstract!s})'

    def __init_subclass__(cls, *args, **kwargs):
        raise TypeError(f"Cannot subclass {cls.__module__}.{cls.__name__}")


_AbcDepTuple = namedtuple('Dep', ('abstract', 'scope', 'default'), defaults=[DepScope.any, Missing])





_pure_dep_defaults = PureDep.scope, PureDep.default



@InjectionMarker.register
@private_setattr
class Dep(_AbcDepTuple):

    """Marks an injectable as a `dependency` to be injected."""
    
    __slots__ = ()

    abstract: T_Injectable
    scope: DepScope
    default: T_Default
    Scope = DepScope

    ANY_SCOPE: t.Final = DepScope.any
    """Inject from any scope.
    """

    ONLY_SELF: t.Final = DepScope.only_self
    """Only inject from the current scope without considering parents
    """

    SKIP_SELF: t.Final = DepScope.skip_self
    """Skip the current scope and resolve from it's parent instead.
    """
    
    def __init_subclass__(cls, *args, **kwargs):
        raise TypeError(f"Cannot subclass {cls.__module__}.{cls.__name__}")

    def __subclasscheck__(self, sub: type) -> bool:
        return sub is PureDep or self._base_subclasscheck(sub)
    
    _base_subclasscheck = _AbcDepTuple.__subclasscheck__

    def __new__(
        cls: type[Self],
        dependency: T_Injectable, 
        scope: DepScope=ANY_SCOPE,
        default=Missing,
    ):  
        if _pure_dep_defaults == (scope, default):
            return PureDep(dependency)
        else:
            return _AbcDepTuple.__new__(cls, dependency, scope, default)

    # @property
    # def __dependency__(self):
    #     return self.__class__

    # @property
    # def __origin__(self):
    #     return self.__class__

    @property
    def has_default(self):
        return not self.default is Missing

    @property
    def injects_default(self):
        return isinstance(self.default, InjectionMarker)





@InjectionMarker.register
class LazyOp(BaseLazyOp[T_Injected]):
    __slots__ = ()

    # """Marks an injectable as a `dependency` to be injected."""

    # __slots__ = (
    #     "__injects__",
    #     "__injector__",
    #     "__v_hashident__",
    #     "__default__",
    # )

    # Flag = DepScope

    # ONLY_SELF: t.Final = DepScope.only_self
    # """Only inject from the current context without considering parents
    # """

    # SKIP_SELF: t.Final = DepScope.skip_self
    # """Skip the current context and resolve from it's parent instead.
    # """

    # _default_metadata = None, Missing, ()

    # def __init_subclass__(cls, *args, **kwargs):
    #     raise TypeError(f"Cannot subclass {cls.__module__}.{cls.__name__}")

    # @t.overload
    # def __new__(
    #     cls: type[Self],
    #     dependency: T_Injectable,
    #     *,
    #     injector: t.Union[DepScope, "Injector", None] = None,
    #     default=Missing,
    # ) -> Self:
    #     ...

    # def __new__(
    #     cls,
    #     dependency: T_Injectable,
    #     injector: t.Union[DepScope, "Injector", None] = None,
    #     default=Missing,
    #     __expr=(),
    # ):
    #     self = super().__new__(cls, __expr)
    #     object.__setattr__(self, "__injects__", dependency)
    #     object.__setattr__(self, "__injector__", injector)
    #     object.__setattr__(self, "__default__", default)
    #     return self

    # @property
    # def __origin__(self):
    #     return self.__class__

    # @property
    # def __metadata__(self):
    #     return self.__injector__, self.__default__, self.__expr__

    # @property
    # def __dependency__(self):
    #     return self.__injects__ if self.__hashident__ is None else self

    # @property
    # def __hasdefault__(self):
    #     return not self.__default__ is Missing

    # @property
    # def __hashident__(self) -> int:
    #     try:
    #         return self.__v_hashident__
    #     except AttributeError:
    #         meta = self.__metadata__
    #         ash = None
    #         if meta == self._default_metadata:
    #             object.__setattr__(self, "__v_hashident__", None)
    #         else:
    #             object.__setattr__(
    #                 self, "__v_hashident__", ash := hash((self.__injects__, meta))
    #             )
    #         return ash

    # def __push__(self, *expr):
    #     return self.__class__(
    #         self.__injects__, self.__injector__, self.__default__, self.__expr__ + expr
    #     )

    # def __reduce__(self):
    #     return self.__class__, (
    #         self.__injects__,
    #         self.__injector__,
    #         self.__default__,
    #         self.__expr__,
    #     )

    # def __eq__(self, x) -> bool:
    #     if not isinstance(x, self.__class__):
    #         return self.__hashident__ is None and x == self.__injects__
    #     return self.__injects__ == x.__injects__ and self.__metadata__ == x.__metadata__

    # def __hash__(self):
    #     ash = self.__hashident__
    #     if ash is None:
    #         return hash(self.__injects__)
    #     else:
    #         return ash

    # def __str__(self):
    #     return f"{self.__injects__!s}" + "".join(map(str, self.__expr__))

    # def __repr__(self) -> bool:
    #     dependency = self.__injects__
    #     injector = self.__injector__
    #     default = self.__default__
    #     return f'{self.__class__.__name__}({dependency=}, {default=}, {injector=}){"".join(map(str, self.__expr__))}'

    # def __setattr__(self, name: str, value) -> None:
    #     getattr(self, name)
    #     raise AttributeError(f"cannot set readonly attribute {name!r}")


from .containers import Container
from .providers import Provider
from .scopes import Scope
