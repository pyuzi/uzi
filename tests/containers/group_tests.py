from collections import abc
import typing as t
import pytest


from uzi._common import FrozenDict


from uzi.containers import BaseContainer, Container, Group
from uzi.markers import ProNoopPredicate, ProPredicate
from uzi.providers import Provider


from ..abc import BaseTestCase


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_T = t.TypeVar("_T")
_T_Ioc = t.TypeVar("_T_Ioc", bound=Group)

_T_FnNew = abc.Callable[..., Group]


class GroupTest(BaseTestCase[_T_Ioc]):

    type_: t.ClassVar[type[_T_Ioc]] = Group

    @pytest.fixture
    def new_args(self, MockContainer):
        return ([MockContainer(name=f"{x}") for x in range(3)],)

    def test_basic(self, new: _T_FnNew, MockContainer):
        conts = [MockContainer(name=f"{x}") for x in range(3)]
        sub = new(conts, name="tname", module="tmodule")
        print(f"{sub=}")
        print(f"{sub.atomic=}")

        assert isinstance(sub, Group)
        assert sub
        assert sub.name == "tname"
        assert sub.module == "tmodule"
        assert sub.qualname == "tmodule:tname"
        assert not sub.is_atomic
        assert isinstance(sub.providers, abc.Mapping)

        assert conts == list(sub.atomic)
        assert all(c in sub.atomic for c in conts)

        str(sub)
        hash(sub)

    def test_contains(self, new: _T_FnNew, MockContainer):
        c1, c2 = (MockContainer() for _ in range(2))
        c1.__contains__.return_value = False
        c2.__contains__.return_value = True
        sub = new([c1, c2])
        assert _T in sub
        c1.__contains__.assert_called_once_with(_T)
        c2.__contains__.assert_called_once_with(_T)

        c2.__contains__.return_value = False

        assert not object in sub
        c1.__contains__.assert_called_with(object)
        c2.__contains__.assert_called_with(object)

    def test_create(self, new: _T_FnNew):
        sub = new()
        assert sub != new(sub.bases)
        assert sub.bases == new(sub.bases).bases

    def test_pro(self, new: _T_FnNew, MockContainer):
        conts = [MockContainer(name=f"{x}") for x in range(4)]
        sub = new(conts)
        pro = sub._evaluate_pro()
        print(sub, *(f"{c}" for c in sub.pro), sep="\n  - ")

        assert isinstance(pro, FrozenDict)
        assert pro == sub.pro
        assert list(pro) == conts

    @xfail(raises=TypeError, strict=True)
    def test_setitem(self, new: _T_FnNew, mock_provider: Provider):
        new()[_T] = mock_provider

    def test_and(self, new: _T_FnNew):
        g1, g2, g3 = new(), new(), new()
        res = g1 & g2 & g3
        assert isinstance(res, ProPredicate)
        assert not isinstance(res, Group)
        pred = ProNoopPredicate()
        assert isinstance(g1 & pred, ProPredicate)
        assert isinstance(pred & g1, ProPredicate)

        # # __iand__
        # sub = new(())
        # orig = sub
        # sub &= g1 & g2 & g3
        # assert sub != orig
        # assert sub.atomic != orig.atomic
        # assert sub.atomic == res.atomic

    def test_invert(self, new: _T_FnNew):
        c1 = new()
        assert isinstance(~c1, ProPredicate)
        assert not isinstance(~c1, Group)

    def test_or(self, new: _T_FnNew, MockContainer):
        g1, g2, g3 = (new([MockContainer() for _ in range(3)]) for __ in range(3))
        res = g1 | g2 | g3
        assert isinstance(res, Group)
        assert list(res.atomic) == [*g1.atomic, *g2.atomic, *g3.atomic]

        pred = ProNoopPredicate()
        for r in (g1 | pred, pred | g1, g1 | pred | g2):
            assert isinstance(r, ProPredicate)
            assert not isinstance(r, BaseContainer)

        # __ior__
        sub = new(())
        orig = sub
        sub |= g1 | g2 | g3
        assert sub != orig
        assert sub.atomic != orig.atomic
        assert sub.atomic == res.atomic

    def test_sub(self, new: _T_FnNew, MockContainer):
        g1, g2 = new([MockContainer() for _ in range(3)]), new(
            [MockContainer() for _ in range(3)]
        )
        g3 = g1 | g2
        sub = g3 - g1
        assert isinstance(sub, Group)
        assert sub.bases == g2.bases

        rem, *rest = g2.bases
        orig = sub
        sub -= rem
        assert orig != sub
        assert isinstance(sub, Group)
        assert list(sub.atomic) == rest

    @xfail(raises=TypeError, strict=True)
    def test_invalid_sub(self, new: _T_FnNew):
        sub = new()
        sub - (new(),)

    def test_extends(self, new: _T_FnNew, MockContainer: type[Container]):
        conts = [MockContainer(name=f"c_{i//3}_{i%3}") for i in range(9)]

        g1, g2, g3 = new(conts[:3]), new(conts[3:6]), new(conts[6:])
        sub = new([g3, *conts[:6]])
        assert sub.extends(g1)
        assert sub.extends(g2)
        assert sub.extends(g3)
        assert all(sub.extends(c) for c in conts)

        sub2 = new([g2, g3])
        assert sub.extends(sub2)
        assert not sub2.extends(sub)

    # def test_access_level(self, new: _T_FnNew):
    #     c1, c2, c3, c4, c5, c6, c7 = tuple(new(f'c{i}') for i in range(7))
    #     c1.extend(c2.extend(c4.extend(c5, c6)))
    #     c1.extend(c3.extend(c5))
    #     assert c1.access_level(c1) is PRIVATE
    #     assert c1.access_level(c7) is PUBLIC
    #     assert c3.access_level(c2) is PUBLIC
    #     assert c1.access_level(c4) is GUARDED
    #     assert c5.access_level(c1) is PROTECTED
