from collections import abc
from functools import wraps
import operator
import typing as t
from abc import ABCMeta, abstractmethod
from inspect import Parameter
from logging import getLogger
from types import FunctionType, GenericAlias, MethodType, new_class
from typing_extensions import Self
from weakref import WeakKeyDictionary, ref

import attr

from ._common import Missing, private_setattr


T_Injected = t.TypeVar("T_Injected", covariant=True)
"""The injected type.
"""

T_Default = t.TypeVar("T_Default")
"""Default value type.
"""

T_Injectable = t.TypeVar("T_Injectable", bound="Injectable", covariant=True)
"""An `Injectable` type.
"""

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
    """Returns `True` if the given type annotation is injectable.
    
    Params: 
        typ (type): The type annotation to check.
    Returns:
        (bool): `True` if `typ` can be injected or `False` if otherwise.
    """
    return isinstance(obj, Injectable) and not (
        obj in _BLACKLIST or isinstance(obj, NonInjectable)
    )


def is_injectable_annotation(typ):
    """Returns `True` if the given type annotation is injectable.
    
    Params: 
        typ (type): The type annotation to check.
    Returns:
        (bool): `True` if `typ` can be injected or `False` if otherwise.
    """
    return is_injectable(typ)



class Injectable(metaclass=ABCMeta):
    """Abstract base class for injectable types.

    An injectable is an object that can be used to represent a dependency.
    
    Builtin injectable types:- `type`, `TypeVar`, `FunctionType`, `MethodType`, 
    `GenericAlias`
    """
    __slots__ = ()


Injectable.register(type)
Injectable.register(t.TypeVar)
Injectable.register(FunctionType)
Injectable.register(MethodType)
Injectable.register(GenericAlias)
Injectable.register(type(t.Generic[T_Injected]))
Injectable.register(type(t.Union))


class NonInjectable(metaclass=ABCMeta):
    """Abstract base class for non-injectable types."""
    __slots__ = ()


NonInjectable.register(_NoneType)
NonInjectable.register(type(t.Literal[1]))




