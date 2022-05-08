import typing as t
import pytest


from collections.abc import Callable
from uzi.graph import NullGraph
from uzi.injectors import NullInjector



from uzi.scopes import NullScope, Scope



from ..abc import BaseTestCase

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_T = t.TypeVar('_T')

_T_FnNew = Callable[..., NullScope]


class NullScopeTests(BaseTestCase[NullScope]):

    type_ = NullScope

    def test_basic(self, new: _T_FnNew):
        sub = new()
        assert isinstance(sub, NullScope)
        assert isinstance(sub, Scope)
        assert sub.parent is None
        assert sub.level == -1
        assert isinstance(sub.graph, NullGraph)
        assert not sub
        assert not sub.container
        str(sub)
        
    def test_compare(self, new: _T_FnNew):
        sub = new()
        assert sub == new()
        assert not sub != new()
        assert not sub is new()
        assert hash(sub) == hash(new())

    @xfail(raises=TypeError, strict=True)
    def test_fail_invalid_getitem(self, new: _T_FnNew):
        new()[2345.6789]
             
    def test_immutable(self, new: _T_FnNew, immutable_attrs):
        self.assert_immutable(new(), immutable_attrs)
 
    def test_injector(self, new: _T_FnNew):
        sub = new()
        assert sub.injector() is sub.injector()
        assert isinstance(sub.injector(), NullInjector)
