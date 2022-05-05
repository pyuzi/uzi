from threading import Lock, Thread
import typing as t
from unittest.mock import MagicMock, Mock, patch
import attr
import pytest


from collections import abc


from xdi.graph import DepGraph
from xdi.scopes import SafeScope, Scope

from .. import checks

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize



_T = t.TypeVar('_T')
_T_FnNew = abc.Callable[..., SafeScope]


from .scope_tests import test_setup_multiple_times, test_reset_multiple_times


@pytest.fixture
def new_args(MockContainer: type[DepGraph]):
    return MockContainer(),

@pytest.fixture
def cls():
    return SafeScope



def test_basic(new: _T_FnNew):
    sub = new()
    assert isinstance(sub, SafeScope)
    



def test_setup(new: _T_FnNew, cls: type[SafeScope], MockInjector):

    N, L = 4, int(1e4)

    def load_fn(s: int=L):
        load = [*range(int(s))]

    def load_mock():
        load_fn()
        inj = MockInjector()
        inj.close =MagicMock(wraps=load_fn)
        return inj

    with patch.object(cls, '_new_injector'):
        cls._new_injector = MagicMock(wraps=load_mock)
        sub = new()

        res = [None] * N
            
        def func(n):
            res[n] = sub.is_active, sub.lock.locked(), sub.injector()

        threads = [Thread(target=func, args=(i,)) for i in range(N)]
        
        *(t.start() for t in threads), 
        *(t.join() for t in threads),
        

        seen = set()
        for i, (active, locked, val) in enumerate(res):
            print(f'{i} -> {active=}, {locked=} {val=}')
            if i == 0:
                assert not active
                assert not locked
            else:
                assert active or locked
                assert val in seen
            seen.add(val)
        
        sub.reset()
        sub._new_injector.assert_called_once()

