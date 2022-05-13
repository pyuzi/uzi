import asyncio
import pytest

import typing as t
from uzi import Dep


from uzi.providers import Factory as Provider


from ..abc import ProviderTestCase, AsyncProviderTestCase, _T_NewPro


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_T_Pro = t.TypeVar("_T_Pro", bound=Provider, covariant=True)
_T_NewPro = _T_NewPro[_T_Pro]


_T = t.TypeVar("_T")
_T_Async = t.TypeVar("_T_Async")


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


class ProviderTestCase(ProviderTestCase[_T_Pro]):
    @pytest.fixture
    def concrete(self):
        def fn(a: Foo, /, b: "Bar", *, z=Dep(Baz, default=None)):
            ...

        return fn

    def test_args_kwargs(self, new: _T_NewPro):
        subject = new()

        args = 1, 2, 3
        kwd = dict(foo=Foo, bar=Bar)

        assert subject.args(*args) is subject
        assert subject.kwargs(**kwd) is subject
        rargs, rkwds = subject.arguments

        assert rargs == args
        assert rkwds == kwd

        args = 4, 5, 7
        subject.args(*args)
        assert (args, kwd) == subject.arguments

        kwd = dict(foobar=122, baz=Baz)
        subject.kwargs(**kwd)
        assert (args, kwd) == subject.arguments


# class AsyncFactoryProviderTests(FactoryProviderTests, AsyncProviderTestCase):

#     @pytest.fixture
#     def graph(self, graph):
#         tval = object()
#         graph[_T] = lambda c: lambda: tval
#         afn = lambda c: lambda: asyncio.sleep(0, tval)
#         afn.is_async = True
#         graph[_T_Async] = afn
#         return graph

#     @pytest.fixture
#     def factory(self, value_setter):
#         async def factory(a: _T, b: _T_Async):
#             assert a is b
#             return await value_setter()
#         return factory
