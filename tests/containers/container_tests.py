from collections import abc
import typing as t
import pytest


from uzi.containers import BaseContainer, Container, Group, ProEntrySet
from uzi.exceptions import ProError
from uzi.markers import (
    GUARDED,
    PRIVATE,
    PROTECTED,
    PUBLIC,
    ProNoopPredicate,
    ProPredicate,
)
from uzi.providers import Provider, ProviderRegistryMixin
from uzi.graph.core import Graph, DepKey


from ..abc import BaseTestCase


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_T = t.TypeVar("_T")
_T_Miss = t.TypeVar("_T_Miss")
_T_Ioc = t.TypeVar("_T_Ioc", bound=Container)

_T_FnNew = abc.Callable[..., Container]


class ContainerTest(BaseTestCase[_T_Ioc]):

    type_: t.ClassVar[type[_T_Ioc]] = Container

    def test_basic(self, new: _T_FnNew):
        sub = new("tname", module="tmodule")
        print(f"{sub=}")

        assert isinstance(sub, Container)
        assert isinstance(sub, ProviderRegistryMixin)
        # assert isinstance(sub.bases, abc.I)

        assert sub
        assert sub.name == "tname"
        assert sub.module == "tmodule"
        assert sub.qualname == "tmodule:tname"
        assert sub.is_atomic
        assert sub[_T] is None
        assert not sub._is_anonymous
        assert not new(None)._is_anonymous
        assert {sub} == set(sub.atomic)
        str(sub)
        hash(sub)

    @xfail(raises=ValueError, strict=True)
    @parametrize("name", ["1abc", " abc", "=xyz", "foo.bar", "foo-bar"])
    def test_create_with_invalid_name(self, new: _T_FnNew, name):
        new(name=name)

    def test_compare(self, new: _T_FnNew):
        c1, c2 = new("c"), new("c")
        assert isinstance(hash(c1), int)
        assert c1 != c2 and not (c1 == c2) and c1.name == c2.name
        assert not c1 == object()
        assert c1 != object()

    def test_immutable(self, new: _T_FnNew, immutable_attrs):
        self.assert_immutable(new(), immutable_attrs)

    def test_and(self, new: _T_FnNew):
        c1, c2, c3 = new("c1"), new("c2"), new("c3")
        assert isinstance(c1 & c2 & c3, ProPredicate)
        assert not isinstance(c1 & c2 & c3, Container)
        pred = ProNoopPredicate()
        assert isinstance(c1 & pred, ProPredicate)
        assert isinstance(pred & c1, ProPredicate)

    def test_invert(self, new: _T_FnNew):
        c1 = new("c1")
        assert isinstance(~c1, ProPredicate)
        assert not isinstance(~c1, Container)

    def test_or(self, new: _T_FnNew):
        c1, c2, c3 = new("c1"), new("c2"), new("c3")
        assert isinstance(c1 | c2 | c3, Group)
        pred = ProNoopPredicate()
        for res in (c1 | pred, pred | c1, c1 | pred | c2):
            assert isinstance(res, ProPredicate)
            assert not isinstance(res, BaseContainer)

    def test_extend(self, new: _T_FnNew):
        c1, c2, c3, c4 = new("c1"), new("c2"), new("c3"), new("c4")
        assert c1.extend(c3).extend(c2.extend(c4), c2) is c1
        assert tuple(c1.bases) == (c3, c2)
        assert tuple(c2.bases) == (c4,)
        assert c1.extends(c1) and c1.extends(c2) and c1.extends(c3) and c1.extends(c4)
        assert not (c2.extends(c1) or c2.extends(c3))

    def test_pro(self, new: _T_FnNew):
        c1, c2, c3, c4, c5, c6 = (
            new("c1"),
            new("c2"),
            new("c3"),
            new("c4"),
            new("c5"),
            new("c6"),
        )
        c1.extend(c2.extend(c4.extend(c5, c6)))
        c1.extend(c3.extend(c5))
        pro = c1._evaluate_pro()
        assert isinstance(pro, ProEntrySet)
        print(*(f"{c}" for c in c1.pro), sep="\n  - ")
        assert pro == c1.pro
        assert tuple(pro) == (c1, c2, c4, c3, c5, c6)

    @xfail(raises=ProError, strict=True)
    def test_inconsistent_pro(self, new: _T_FnNew):
        c1, c2, c3 = new("c1"), new("c2"), new("c3")
        c1.extend(c3, c2.extend(c3))
        c1.pro

    def test_pro_entries(self, new: _T_FnNew):
        c1, c2, c3, c4, c5, c6, *_ = containers = tuple(new(f"c{i}") for i in range(10))
        c1.extend(c2.extend(c4.extend(c5, c6)))
        c1.extend(c3.extend(c5))

        assert c1.pro_entries(containers, None, None) == containers[:6]
        assert c1.pro_entries(containers[3:], None, None) == containers[3:6]
        assert all(c in c1.pro for c in c1.pro_entries(containers, None, None))

    def test_extends(self, new: _T_FnNew):
        sub, c1, c2, c3, c4 = new(), new("c1"), new("c2"), new("c3"), new("c4")

        sub.extend(c1, c2.extend(c3))

        assert all(sub.extends(c) for c in (sub, c1, c2, c3))
        assert not sub.extends(c4)
        assert sub.extends(c1 | c2)
        assert sub.extends(c1 | c3)
        assert sub.extends(sub | c1 | c2 | c3)
        assert not sub.extends(c1 | c4)
        assert not sub.extends(sub | c4 | c2)

    def test_access_modifier(self, new: _T_FnNew):
        c1, c2, c3, c4, c5, c6, c7 = tuple(new(f"c{i}") for i in range(7))
        c1.extend(c2.extend(c4.extend(c5, c6)))
        c1.extend(c3.extend(c5))
        assert c1.access_modifier(c1) is PRIVATE
        assert c1.access_modifier(c7) is PUBLIC
        assert c3.access_modifier(c2) is PUBLIC
        assert c1.access_modifier(c4) is GUARDED
        assert c5.access_modifier(c1) is PROTECTED

    def test_setitem(self, new: _T_FnNew, mock_provider: Provider):
        sub = new()
        assert not _T in sub
        sub[_T] = mock_provider
        assert _T in sub
        assert sub[_T] is mock_provider
        mock_provider.container is sub
        mock_provider._setup.assert_called_once_with(sub, _T)

    @xfail(raises=TypeError, strict=True)
    def test_invalid_setitem(self, new: _T_FnNew, mock_provider: Provider):
        new()["sddsdsds"] = mock_provider

    def test_getitem(self, new: _T_FnNew, mock_provider: Provider):
        sub = new()
        sub[_T] = mock_provider
        assert sub[_T] is mock_provider
        assert sub[_T_Miss] is None

    def test_missing(self, new: _T_FnNew, MockProvider: type[Provider]):
        sub = new()
        pro1, pro2, pro3 = (MockProvider() for _ in range(3))
        pro3.container = new()
        sub[_T] = pro1
        assert sub[_T] is pro1
        assert sub[_T_Miss] is None
        assert sub[pro1] is pro1
        assert sub[pro2] is pro2
        assert sub[pro3] is None

    def test__resolve(
        self,
        new: _T_FnNew,
        mock_graph: Graph,
        MockDepKey: type[DepKey],
        MockProvider: type[Provider],
    ):
        T1, T2, T3, T4 = (
            t.TypeVar("T1"),
            t.TypeVar("T2"),
            t.TypeVar("T3"),
            t.TypeVar("T4"),
        )
        c1, c2, c3 = new("child"), new("subject"), new("base")
        c1.extend(c2.extend(c3))
        c2[T1] = MockProvider(access_modifier=PRIVATE)
        kt1 = MockDepKey(abstract=T1, container=c1)

        assert tuple(c2._resolve(kt1, mock_graph)) == ()

        c2[T1].access_modifier = GUARDED
        assert tuple(c2._resolve(kt1, mock_graph)) == ()

        c2[T1].access_modifier = PROTECTED
        assert tuple(c2._resolve(kt1, mock_graph)) == (c2[T1],)

        c2[T1].access_modifier = PUBLIC
        assert tuple(c2._resolve(kt1, mock_graph)) == (c2[T1],)

        c2[T1]._can_resolve.assert_called_with(kt1, mock_graph)

        c2[T1].access_modifier = PRIVATE
        kt1.container = c3

        assert tuple(c2._resolve(kt1, mock_graph)) == ()

        c2[T1].access_modifier = GUARDED
        assert tuple(c2._resolve(kt1, mock_graph)) == (c2[T1],)

        c2[T1].access_modifier = PROTECTED
        assert tuple(c2._resolve(kt1, mock_graph)) == (c2[T1],)

        c2[T1].access_modifier = PUBLIC
        assert tuple(c2._resolve(kt1, mock_graph)) == (c2[T1],)

        c2[T1]._can_resolve.assert_called_with(kt1, mock_graph)

        c2[T1].access_modifier = PRIVATE
        kt1.container = c2

        assert tuple(c2._resolve(kt1, mock_graph)) == (c2[T1],)
