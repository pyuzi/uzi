import typing as t
from abc import ABCMeta
from inspect import Parameter
from logging import getLogger
from types import FunctionType, GenericAlias, MethodType

import attr

from ._common import Missing

if t.TYPE_CHECKING:
    from .providers import Provider

    ProviderType = type[Provider]


T_Injected = t.TypeVar("T_Injected", covariant=True)
T_Default = t.TypeVar("T_Default")
T_Injectable = t.TypeVar("T_Injectable", bound="Injectable", covariant=True)


logger = getLogger(__name__)

_NoneType = type(None)


_BLACKLIST = frozenset(
    {
        None,
        _NoneType,
        t.Any,
        type(t.Literal[1]),
        str,
        bytes,
        bytearray,
        tuple,
        int,
        float,
        frozenset,
        set,
        dict,
        list,
        Parameter.empty,
        Missing,
    }
)


def is_injectable(obj):
    return isinstance(obj, Injectable) and not (
        obj in _BLACKLIST or isinstance(obj, NonInjectable)
    )


def is_injectable_annotation(obj):
    """Returns `True` if the given type is injectable."""
    return is_injectable(obj)


@attr.s()
class InjectorLookupError(KeyError):

    abstract: "Injectable" = attr.ib(default=None)
    scope: "Scope" = attr.ib(default=None)


class Injectable(metaclass=ABCMeta):

    __slots__ = ()


Injectable.register(type)
Injectable.register(t.TypeVar)
Injectable.register(FunctionType)
Injectable.register(MethodType)
Injectable.register(GenericAlias)
Injectable.register(type(t.Generic[T_Injected]))
Injectable.register(type(t.Union))


class NonInjectable(metaclass=ABCMeta):
    __slots__ = ()


NonInjectable.register(_NoneType)
NonInjectable.register(type(t.Literal[1]))



from .makers import Dep, InjectionMarker, Provided, PureDep

from . import injectors, providers
from .containers import Container
from .injectors import Injector
from .providers import Provider
from .scopes import Scope
