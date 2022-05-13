from inspect import signature
import typing as t
import pytest


from collections import abc
from uzi import Dep


from uzi._functools import BoundParams, BoundParam
from uzi.graph.core import Graph


from ..abc import BaseTestCase

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


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


class BoundParamsTests(BaseTestCase[BoundParams]):
    def test__iter_bind(self, cls: type[BoundParams], mock_graph: Graph):
        def func(foo: Foo, /, *args, bar: Bar, baz: Baz = None, **kwds):
            pass

        it = cls._iter_bind(
            signature(func),
            mock_graph,
            args=(Dep(Foo), "arg_1"),
            kwargs=dict(kwarg="keyword"),
        )
        assert isinstance(it, abc.Iterator)
        ls = [*it]
        assert all(isinstance(p, BoundParam) for p in ls)
        for i, n in enumerate(["foo", "args", "bar", "baz", "kwds"]):
            assert ls[i].name == n

    def test_bind(self, cls: type[BoundParams], mock_graph: Graph):
        def func(foo: Foo, /, *args, bar: Bar, baz: Baz = None, **kwds):
            pass

        sub = cls.bind(
            signature(func),
            mock_graph,
            args=(Dep(Foo), "arg_1"),
            kwargs=dict(kwarg="keyword"),
        )
        assert isinstance(sub, cls)

    def test_make(self, cls: type[BoundParams], mock_graph: Graph):
        def func(
            foo: Foo,
            x=None,
            /,
            *args,
            bar: Bar,
            baz: Baz = None,
            foobar=Dep(FooBar),
            **kwds,
        ):
            pass

        it = cls._iter_bind(
            signature(func),
            mock_graph,
            args=(Dep(Foo), "arg_1"),
            kwargs=dict(kwarg="keyword"),
        )
        sub = cls.make(it)
        assert isinstance(sub, cls)
