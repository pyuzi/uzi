from unittest.mock import Mock

import pytest
from laza.common.collections import Arguments
from laza.di import Dep, Injector
from laza.di.providers.functools import FactoryResolver

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


class FactoryResolverTests:

    cls = FactoryResolver

    @parametrize(
        ["fn", "args", "kwds", "exp"],
        [
            (lambda a, b, c: ..., ("A", "B", "C"), {}, dict(a="A", b="B", c="C")),
            (
                lambda a, b, c: ...,
                (),
                dict(a="A", b="B", c="C"),
                dict(a="A", b="B", c="C"),
            ),
            (
                lambda x, *p, k, **kw: ...,
                ("X", 1, 2),
                dict(k="K", y="Y", z="Z"),
                dict(x="X", p=(1, 2), k="K", kw=dict(y="Y", z="Z")),
            ),
        ],
    )
    def test_arguments(self, fn, args, kwds, exp):
        res = self.cls(fn, arguments=Arguments(args, kwds))
        assert res.arguments == exp

    def test_call(self, injector: Injector, context: dict):
        def foo(obj: object, a: int = 1, *, k=Dep(str), kw: list):
            return obj, a, k, kw

        vals = object(), 11, "The K", [1, 2, 3]

        res = self.cls(foo, arguments=Arguments.make(a=vals[1]))
        context.update({
            object: lambda: vals[0],
            Dep(str): lambda: vals[2],
            list: lambda: vals[3],
        })

        injector.is_provided = Mock(side_effect=lambda o: o in context)

        rfn, deps = res(injector, foo)
        assert callable(rfn)
        assert deps == {object: ["obj"], list: ["kw"], Dep(str): ["k"]}
        fn = rfn(context)
        assert callable(fn)
        v = fn()
        assert v == vals
