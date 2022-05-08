from inspect import Parameter, signature
from itertools import chain
from os import sep
import typing as t
import attr
import pytest

from unittest.mock import  MagicMock, Mock

from collections.abc import Callable, Iterator, Set, MutableSet
from uzi import Dep
from uzi._common import FrozenDict


from uzi._functools import BoundParam
from uzi.graph import DepGraph



from ..abc import BaseTestCase

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_T = t.TypeVar('_T')
_T_Scp = t.TypeVar('_T_Scp', bound=DepGraph)

_T_FnNew = Callable[..., _T_Scp]


class Foo:
    def __init__(self) -> None:
        pass


class Bar:
    def __init__(self) -> None:
        pass


class Baz:
    def __init__(self) -> None:
        pass


class FooBar:
    def __init__(self) -> None:
        pass



class BoundParamTests(BaseTestCase[BoundParam]):

    type_: t.ClassVar[type[_T_Scp]] = BoundParam

    def test_basic(self, cls: type[BoundParam]):
        value = object()
        default=object()
        param = Parameter('foo', Parameter.POSITIONAL_ONLY, annotation=Foo, default=default)
        sub = cls(param, value)
        assert isinstance(sub, cls)
        assert sub.param is param
        assert sub.name is param.name
        assert sub.kind is param.kind
        assert sub.annotation is param.annotation
        assert sub.has_default
        assert sub.has_value
        assert sub.is_injectable
        assert sub.value is value
        assert sub.default is default
    
    def test_value(self,  cls: type[BoundParam]):
        value = object()
        sub = cls(Parameter('foo', Parameter.POSITIONAL_ONLY), value)
        assert sub.has_value
        assert sub.value is value

    def test_value_injectable(self, cls: type[BoundParam]):
        value = Dep(Foo)
        sub = cls(Parameter('foo', Parameter.POSITIONAL_ONLY, default=Dep(Bar), annotation=Baz), value)
        assert not sub.has_value
        assert not sub.has_default
        assert sub.is_injectable
        assert sub.injectable is value

    def test_default_injectable(self, cls: type[BoundParam]):
        default=Dep(Bar)
        sub = cls(Parameter('foo', Parameter.POSITIONAL_ONLY, default=default, annotation=Baz), object())
        assert sub.is_injectable
        assert sub.has_value
        assert not sub.has_default
        assert sub.injectable is default

    def test_annotation_injectable(self, cls: type[BoundParam]):
        sub = cls(Parameter('foo', Parameter.POSITIONAL_ONLY, default=object(), annotation=Baz), object())
        assert sub.is_injectable
        assert sub.has_value
        assert sub.has_default
        assert sub.injectable is Baz

    