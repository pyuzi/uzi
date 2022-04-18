import typing as t
import attr
import pytest


from collections.abc import Callable, Iterator, Set, MutableSet
from xdi._common import frozendict


from xdi.scopes import NullScope, Scope



from ..abc import BaseTestCase

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_T = t.TypeVar('_T')
_T_Scp = t.TypeVar('_T_Scp', bound=Scope)

_T_FnNew = Callable[..., _T_Scp]



class NullScopeTests(BaseTestCase[NullScope]):

    type_: t.ClassVar[type[_T_Scp]] = NullScope

    def test_basic(self, new: _T_FnNew):
        sub = new()
        assert isinstance(sub, NullScope)
        assert isinstance(sub, frozendict)
        assert isinstance(sub.maps, Set)
        assert not isinstance(sub.maps, MutableSet)
        assert sub.parent is None
        assert sub.level == -1
        assert not sub
        assert not sub.container
        assert not sub.maps
        str(sub)
        
    def test_compare(self, new: _T_FnNew):
        sub = new()
        assert sub == NullScope()
        assert not sub != NullScope()
        assert not sub is NullScope()
        assert hash(sub) == hash(NullScope())

    def test_is_blank(self, new: _T_FnNew):
        sub = new()
        assert len(sub) == 0
        assert sub[_T] is None
        assert not _T in sub
     
    def test_immutable(self, new: _T_FnNew, immutable_attrs):
        self.assert_immutable(new(), immutable_attrs)
