import asyncio
from threading import Thread
import typing as t
from unittest.mock import MagicMock, patch
import pytest


from collections import abc


from uzi.graph import Graph
from uzi.scopes import ContextLocalScope


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_T = t.TypeVar('_T')
_T_FnNew = abc.Callable[..., ContextLocalScope]


from .scope_tests import test_push_pop_multiple_times, test_push_multiple_times, test_pop_multiple_times


@pytest.fixture
def new_args(MockContainer: type[Graph]):
    return MockContainer(),

@pytest.fixture
def cls():
    return ContextLocalScope



async def test_multiple(new: _T_FnNew, cls: type[ContextLocalScope], MockInjector):

    N, L = 5, int(1e4)

    with patch.object(cls, '_new_injector'):
        cls._new_injector = MagicMock(wraps=MockInjector)
        sub = new()

        res = [None] * N
            
        async def func(n):
            res[n] = sub.active, sub.injector()

        tasks = [func(i) for i in range(N)]
        
        await asyncio.gather(*tasks)
        
        assert not sub.active

        seen = set()
        for i, (active, val) in enumerate(res):
            print(f'{i} -> {active=}, {val=}')
            assert not active
            assert not val in seen
            seen.add(val)

        assert sub._new_injector.call_count == N



async def test_multiple_with_parent_context(new: _T_FnNew, cls: type[ContextLocalScope], MockInjector):

    N, L = 5, int(1e4)

    with patch.object(cls, '_new_injector'):
        cls._new_injector = MagicMock(wraps=MockInjector)
        sub = new()

        res = [None] * N
            
        async def func(n):
            res[n] = sub.active, sub.injector()

        tasks = [func(i) for i in range(N)]

        inj = sub.push()

        await asyncio.gather(*tasks)
        
        seen = set()
        for i, (active, val) in enumerate(res):
            assert active
            assert val is inj
            assert not i or val in seen
            seen.add(val)

        sub._new_injector.assert_called_once()
        sub.pop()




def test_in_multithread_setup(new: _T_FnNew, cls: type[ContextLocalScope], MockInjector):

    N, L = 4, int(1e4)

    with patch.object(cls, '_new_injector'):
        cls._new_injector = MagicMock(wraps=MockInjector)
        sub = new()

        res = [None] * N
            
        def func(n):
            res[n] = sub.active, sub.injector()

        with sub as inj:

            threads = [Thread(target=func, args=(i,)) for i in range(N)]
            
            *(t.start() for t in threads), 
            *(t.join() for t in threads),

            seen = {inj}
            for i, (active, val) in enumerate(res):
                print(f'{i} -> {active=}, {val=}')
                assert not active
                assert not val in seen
                seen.add(val)
            

        assert not sub.active
        assert sub._new_injector.call_count == N + 1

