from copy import copy, deepcopy
import pytest


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


from uzi._common.lookups import (
    Lookup,
    EvaluationError,
    AttributeEvaluationError,
    KeyEvaluationError,
    IndexEvaluationError,
    CallEvaluationError,
)


class SomeKeyError(KeyError):

    ...


_T_New = type[Lookup]


def test_evaluationerror_wrap():
    exc = EvaluationError.wrap(SomeKeyError("err!"))
    assert isinstance(exc, EvaluationError)
    assert isinstance(exc, KeyEvaluationError)
    exc = KeyEvaluationError.wrap(SomeKeyError("err!"))
    assert isinstance(exc, KeyEvaluationError)


class LookupTests:
    @pytest.fixture
    def new(self):
        return Lookup

    def test_basic(self, new: _T_New):
        str(new().a["xyz"].b(1, 2).c[0:])
        assert isinstance(new(), Lookup)
        assert new().a and new()[0] and new()["abc"] and new()[:0] and new()()

    def test_compare(self, new: _T_New):
        s1, s2 = new().a.b(1, 2).c[0:], new().a.b(1, 2).c[0:]
        assert s1 == s2
        assert not s1 != s2
        assert s1 != new().a.b(1, 2).c

    def test_copy(self, new: _T_New):
        s1 = new().a["xyz"].b(1, 2).c[0:]
        cp = copy(s1)
        assert s1 == cp
        assert s1.__class__ is cp.__class__

    def test_deepcopy(self, new: _T_New):
        s1 = new().a["xyz"].b(1, 2).c[0:]
        cp = deepcopy(s1)
        assert s1 == cp
        assert s1.__class__ is cp.__class__

    def test_eval(self, new):
        class Foo:
            a = dict(list=list(range(10)), data=dict(bee="Im a bee"))

            class bar:
                @classmethod
                def run(cls, *args, **kwargs) -> None:
                    print(f"ran with({args=}, {kwargs=})")
                    return Foo

        p = new().a["list"][2:-2]
        val = p.__eval__(Foo)
        assert val == Foo.a["list"][2:-2]
        # print(f'{p!r}', f'{p}  --> {val!r}', sep='\n ')

        p = new().bar.run(1, 2, 3, k1=1, k2=2).a["list"][2:-2]
        val = p.__eval__(Foo)
        assert val == Foo.bar.run(1, 2, 3, k1=1, k2=2).a["list"][2:-2]
        # print(f'{p!r}', f'{p}  --> {val!r}', sep='\n ')

        # assert 0

    @xfail(raises=AttributeEvaluationError, strict=True)
    def test_missing_attribute(self, new):
        class Foo:
            a = dict(list=list(range(10)), data=dict(bee="Im a bee"))

        new().a.list.__eval__(Foo)

    @xfail(raises=KeyEvaluationError, strict=True)
    def test_missing_key(self, new):
        class Foo:
            a = dict(list=list(range(10)), data=dict(bee="Im a bee"))

        new().a["abcd"].__eval__(Foo)

    @xfail(raises=IndexEvaluationError, strict=True)
    def test_missing_index(self, new):
        class Foo:
            a = dict(list=list(range(10)), data=dict(bee="Im a bee"))

        new().a["list"][100].__eval__(Foo)

    @xfail(raises=CallEvaluationError, strict=True)
    def test_missing_none_callable(self, new):
        class Foo:
            a = dict(list=list(range(10)), data=dict(bee="Im a bee"))

        new().a["list"]().__eval__(Foo)
