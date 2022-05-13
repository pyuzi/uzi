from threading import Lock, Thread
import typing as t
from unittest.mock import MagicMock, Mock, patch
import attr
import pytest


from collections import abc


from uzi.graph import Graph
from uzi.scopes import ThreadLocalScope, Scope

from .. import checks

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_T = t.TypeVar('_T')
_T_FnNew = abc.Callable[..., ThreadLocalScope]


from .scope_tests import test_push_pop_multiple_times, test_push_multiple_times, test_pop_multiple_times


@pytest.fixture
def new_args(MockContainer: type[Graph]):
    return MockContainer(),

@pytest.fixture
def cls():
    return ThreadLocalScope




def test_multithread(new: _T_FnNew, cls: type[ThreadLocalScope], MockInjector):

    N, L = 4, int(1e4)

    def load_fn(s: int=L):
        load = [*range(int(s))]

    def load_mock():
        load_fn()
        inj = MockInjector()
        inj.close =MagicMock(wraps=load_fn)
        return inj
    
    def func(sub: cls, res, n):
        res[n] = sub.active, sub.injector()


    with patch.object(cls, '_new_injector'):
        cls._new_injector = MagicMock(wraps=load_mock)
        sub = new()

        res = [None] * N
        threads = [Thread(target=func, args=(sub, res, i)) for i in range(N)]
            
        *(t.start() for t in threads), 
        *(t.join() for t in threads),
        
        assert not sub.active        
        inj = sub.push()

        seen = set()
        for i, (active, val) in enumerate(res):
            print(f'{i} -> {active=}, {val=}')
            if i == 0:
                assert not active
            else:
                assert not val in seen
            assert not val is inj
            seen.add(val)

        assert len(seen) == N
        assert sub._new_injector.call_count == N + 1

