from copy import copy
import typing as t
from unittest.mock import MagicMock
import attr
import pytest


from collections.abc import Callable, Iterator, Set, MutableSet
from xdi import InjectorLookupError
from xdi._common import frozendict
from xdi.injectors import Injector, NullInjector
from xdi._dependency import SimpleDependency, Dependency, LookupErrorDependency


from xdi.scopes import NullScope, Scope



from ..abc import BaseTestCase

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_T = t.TypeVar('_T')
_T_Inj = t.TypeVar('_T_Inj', bound=Injector)

_T_FnNew = Callable[..., _T_Inj]

_T_Miss =  t.TypeVar('_T_Miss')



class InjectorTests(BaseTestCase[Injector]):

    @pytest.fixture
    def mock_scope(self, mock_scope):
        mock_scope[_T_Miss] = LookupErrorDependency(_T_Miss, mock_scope)
        return mock_scope

    @pytest.fixture
    def new_args(self, mock_scope):
        return (mock_scope,)

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
        assert sub == new() == copy(sub)
        assert not sub != new()
        assert not sub == object()
        assert sub != object()
        assert hash(sub) == hash(new())
    
    def test_immutable(self, new: _T_FnNew, immutable_attrs):
        self.assert_immutable(new(), immutable_attrs)

    @xfail(raises=InjectorLookupError, strict=True)
    @parametrize('key', [
        _T_Miss, 
        SimpleDependency(_T_Miss, NullScope(), concrete=MagicMock(_T_Miss))
    ])
    def test_lookup_error(self, new: _T_FnNew, key):
        sub = new()
        assert not key in sub
        if isinstance(key, Dependency):
            new()[key]
        else:
            sub.make(key)

   
       