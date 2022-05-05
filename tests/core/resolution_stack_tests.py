from asyncio import gather, sleep
from copy import copy, deepcopy
import pickle
import typing as t
import attr
import pytest


from collections import abc


from xdi.providers import Provider
from xdi.graph import ResolutionStack



from ..abc import BaseTestCase
from .. import assertions

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_T = t.TypeVar('_T')

_T_FnNew = abc.Callable[..., ResolutionStack]

   

@pytest.fixture
def new_args(mock_container):
    return mock_container,

@pytest.fixture
def cls():
    return ResolutionStack




def test_basic(new: _T_FnNew, mock_container, mock_provider: Provider, MockContainer):
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


async def test_multiple_contexts(new: _T_FnNew, mock_container, MockProvider: type[Provider], MockContainer):
    sub = new()

    cont1, cont2 = MockContainer(), MockContainer()
    prov1, prov2 = MockProvider(container=cont1), MockProvider(container=cont2),
    pushes = 0

    async def test(prov: Provider, x):
        nonlocal pushes
        with sub.push(prov, _T):
            pushes += 1
            await sleep(.0001)
            assert pushes == 2
            assert len(sub) ==  2
            assert sub.top.container is prov.container
            assert sub.top.abstract is _T
            assert sub.top.provider is prov
            assert x not in sub

    await gather(test(prov1, prov2), test(prov2, prov1))


@xfail(raises=ValueError, strict=True)
def test_index_value_error(new: _T_FnNew, mock_provider: Provider):
    sub = new()
    assert mock_provider not in sub
    sub.index(mock_provider)



@xfail(raises=TypeError, strict=True)
def test_copy(new: _T_FnNew):
    copy(new())


@xfail(raises=TypeError, strict=True)
def test_deepcopy(new: _T_FnNew):
    deepcopy(new())


@xfail(raises=TypeError, strict=True)
def test_pickle(new: _T_FnNew):
    pickle.dumps(new())


@xfail(raises=ValueError, strict=True)
def test_invalid_pop(new: _T_FnNew, mock_provider: Provider):
    sub = new()
    sub.push(mock_provider)
    res = sub.pop()
    assert res.provider is mock_provider
    sub.pop()
    