import typing as t
import attr
import pytest


from collections.abc import Callable, Iterator, Set, MutableSet
from xdi import InjectorLookupError
from xdi._common import frozendict
from xdi.injectors import Injector, NullInjector


from xdi.scopes import NullScope, Scope



from ..abc import BaseTestCase

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_T = t.TypeVar('_T')
_T_Inj = t.TypeVar('_T_Inj', bound=NullInjector)

_T_FnNew = Callable[..., _T_Inj]



class NullInjectorTests(BaseTestCase[NullInjector]):

    @pytest.fixture(params=[a for a in dir(NullInjector) if a[:1] != '_'])
    def attribute(self, request):
        return request.param

    def test_basic(self, new: _T_FnNew):
        sub = new()
        assert isinstance(sub, Injector)
        assert isinstance(sub, NullInjector)
        assert isinstance(sub, frozendict)
        assert isinstance(sub.scope, Scope)
        assert sub.parent is None
        assert not sub
        assert not sub.scope
        str(sub)
        
    def test_compare(self, new: _T_FnNew):
        sub = new()
        assert sub == new()
        assert not sub != new()
        assert not sub == object()
        assert sub != object()
        assert hash(sub) == hash(new())

    def test_is_blank(self, new: _T_FnNew):
        sub = new()
        assert len(sub) == 0
        assert not _T in sub

    @xfail(raises=InjectorLookupError, strict=True)
    def test_lookup_error(self, new: _T_FnNew, attribute):
        new()[_T]
       
    @xfail(raises=AttributeError, strict=True)
    def test_immutable(self, new: _T_FnNew, attribute):
        sub = new()
        setattr(sub, attribute, getattr(sub, attribute, None))
       
       