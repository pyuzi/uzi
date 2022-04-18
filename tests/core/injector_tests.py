import typing as t
import attr
import pytest


from collections.abc import Callable, Iterator, Set, MutableSet
from xdi._common import frozendict
from xdi.injectors import Injector, NullInjector


from xdi.scopes import Scope



from ..abc import BaseTestCase

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_T = t.TypeVar('_T')
_T_Inj = t.TypeVar('_T_Inj', bound=Injector)

_T_FnNew = Callable[..., _T_Inj]




class InjectorTests(BaseTestCase[Injector]):

    @pytest.fixture
    def new_args(self, mock_scope):
        return (mock_scope,)

    @pytest.fixture(params=[a for a in dir(Injector) if a[:1] != '_'])
    def attribute(self, request):
        return request.param

    def test_basic(self, new: _T_FnNew):
        sub = new()
        assert isinstance(sub, Injector)
        assert isinstance(sub, frozendict)
        assert isinstance(sub.scope, Scope)
        assert isinstance(sub.parent, Injector)
        assert sub
        str(sub)
        
    def test_compare(self, new: _T_FnNew):
        sub = new()
        assert sub == new()
        assert not sub != new()
        assert not sub == object()
        assert sub != object()
        assert hash(sub) == hash(new())

    @xfail(raises=AttributeError, strict=True)
    def test_immutable(self, new: _T_FnNew, attribute):
        sub = new()
        setattr(sub, attribute, getattr(sub, attribute, None))
       
       