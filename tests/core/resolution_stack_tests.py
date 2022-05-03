from inspect import ismethod
import typing as t
import attr
import pytest

from unittest.mock import  MagicMock, Mock

from collections.abc import Callable, Iterator, Set, MutableSet, Mapping
from xdi._common import FrozenDict, ReadonlyDict


from xdi import is_injectable
from xdi.containers import Container
from xdi.exceptions import FinalProviderOverrideError, ProError
from xdi.markers import DepKey
from xdi.providers import Provider
from xdi._bindings import Binding
from xdi.scopes import NullScope, ResolutionStack, Scope



from ..abc import BaseTestCase
from .. import assertions

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_T = t.TypeVar('_T')
_T_Scp = t.TypeVar('_T_Scp', bound=Scope)

_T_FnNew = Callable[..., ResolutionStack]

   
   
# class ScopeTest(BaseTestCase[_T_Scp]):

# type_: t.ClassVar[type[_T_Scp]] = Scope

@pytest.fixture
def new_args(mock_container):
    return mock_container,

@pytest.fixture
def cls():
    return ResolutionStack




def test_resolution_stack(new: _T_FnNew, mock_container, mock_provider: Provider, MockContainer):
    sub = new()

    assert sub
    assert isinstance(sub, ResolutionStack)
    assert isinstance(sub.top, ResolutionStack.StackItem)
    assert len(sub) == 1
    
    assert sub.top.container is mock_container
    assert mock_container in sub
    assert sub.index(mock_container) == 0

    mock_provider.container = prov_container = MockContainer()

    with sub.push(mock_provider, _T):
        assert sub.top.container is prov_container
        assert sub.top.abstract is _T
        assert sub.top.provider is mock_provider
        assert all(x in sub for x in (prov_container, _T, mock_provider, (prov_container, _T, mock_provider), mock_container))
        assert all(sub.index(x) == 0 for x in (prov_container, _T, mock_provider, (prov_container, _T, mock_provider)))
        assert sub.index(mock_container) == 1
        assert len(sub) == 2
        assert [*sub][::-1] == [*reversed(sub)]
    
    assert sub.top.container is mock_container
    assert len(sub) == 1



@xfail(raises=ValueError, strict=True)
def test_resolution_stack_index_valueerror(new: _T_FnNew, mock_provider: Provider):
    sub = new()
    assert mock_provider not in sub
    sub.index(mock_provider)