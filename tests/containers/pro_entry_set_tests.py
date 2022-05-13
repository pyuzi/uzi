from collections import abc
import typing as t
import pytest




from uzi.containers import AtomicProEntrySet, ProEntrySet



xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize

_T_FnNew = type[ProEntrySet]


@pytest.fixture(params=[ProEntrySet, AtomicProEntrySet])
def cls(request: pytest.FixtureRequest):
    return request.param
    

    
@pytest.fixture
def new_args(MockContainer, MockGroup):
    ret =[ 
        MockGroup(), 
        *(MockContainer() for x in range(3)), 
        MockGroup()
    ]
    return ret,

@pytest.fixture
def new(cls: type[ProEntrySet], new_args):
    def make(*a, **kw):
        return cls.make(*a, *new_args[len(a):], **kw)
    return make

def test_basic(new: _T_FnNew):
    sub = new()
    assert isinstance(sub, ProEntrySet)
    print(f'{sub=}', *sub, sep='\n  - ')
    hash(sub)
    assert sub == sub.fromkeys(sub)
    assert not sub == dict(sub)
    assert sub != dict(sub)
    assert sub != list(sub)
    assert not sub == list(sub)
    assert sub != sub.fromkeys(reversed(sub))
    assert sub.atomic() == AtomicProEntrySet.atomic(sub)
    
    if sub.is_atomic:
        assert sub.atomic() is sub
    else:
        assert [*sub.atomic()] != [*sub]

