import typing as t
import pytest


from collections.abc import Callable


from uzi.graph import NullGraph, DepGraph



from ..abc import BaseTestCase

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_T = t.TypeVar('_T')
_T_Scp = t.TypeVar('_T_Scp', bound=DepGraph)

_T_FnNew = Callable[..., _T_Scp]


class NullGraphTests(BaseTestCase[NullGraph]):

    type_: t.ClassVar[type[_T_Scp]] = NullGraph

    def test_basic(self, new: _T_FnNew):
        sub = new()
        assert isinstance(sub, NullGraph)
        assert isinstance(sub, DepGraph)
        assert sub.parent is None
        assert sub.level == -1
        assert not sub
        assert not sub.container
        assert not sub.pros
        assert not sub.extends(new())
        str(sub)
        
    def test_compare(self, new: _T_FnNew):
        sub = new()
        assert sub == NullGraph()
        assert not sub != NullGraph()
        assert not sub is NullGraph()
        assert hash(sub) == hash(NullGraph())

    def test_is_blank(self, new: _T_FnNew):
        sub = new()
        assert len(sub) == 0
        assert not sub[_T]
        assert not _T in sub

    @xfail(raises=TypeError, strict=True)
    def test_fail_invalid_getitem(self, new: _T_FnNew):
        new()[2345.6789]
             
    def test_immutable(self, new: _T_FnNew, immutable_attrs):
        self.assert_immutable(new(), immutable_attrs)
