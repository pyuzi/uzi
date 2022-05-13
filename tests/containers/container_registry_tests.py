from collections import abc, defaultdict
from itertools import groupby
import re
import typing as t
from unittest.mock import MagicMock, patch
import pytest



from uzi._common import ReadonlyDict


from uzi.containers import _ContainerRegistry, Container, Group



xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize

_T_FnNew = type[_ContainerRegistry]

@pytest.fixture
def cls():
    return _ContainerRegistry 

    

def test_basic(new: _T_FnNew, MockContainer: type[Container], MockGroup: type[Group]):
    sub = new()
    assert isinstance(sub, _ContainerRegistry)
    assert isinstance(sub, ReadonlyDict)
    print(f'{sub=}')

    con, con0 = MockContainer(), MockContainer(_is_anonymous=True),
    grp, grp0 = MockGroup(), MockGroup(_is_anonymous=True)
    sub.add(con, con0)
    sub.add(grp0, grp)
    assert con in sub
    assert grp in sub
    assert not con0 in sub
    assert not grp0 in sub
    assert con.qualname in sub
    assert grp.qualname in sub
    assert sub.get('zxcvbnmfghjkl') is None
    assert not 'zxcvbnmfghjkl' in sub

    assert sub[con.qualname] == sub.get(con.qualname)
    assert con in sub[con.qualname]
    assert grp in sub[grp.qualname]
    
    assert [*sub.all()] == [con, grp] 

    



def test_all(new: _T_FnNew, MockContainer: type[Container], MockGroup: type[Group]):
    items: dict[str,  dict[t.Union[Container, Group], None]] = defaultdict(dict)
    N = 3
    for test in range(N):
        mod = f'{__package__}.mod_{test}'
        mocks = (
            MockContainer(name='test', module=mod), 
            MockGroup(name='test', module=mod),
            MockGroup(name=f'g0', module=mod),
            MockContainer(name=f'c0', module=mod),
        )
        print(f' - {mod}')
        for test in mocks:
            items[test.qualname].setdefault(test)
            print(f'     - {test.qualname}')


    values = {i: None for g in items.values() for i in g.keys()}
    mods = {i.module: None for g in items.values() for i in g.keys()}.keys()

    sub = new()
    sub.add(*values)
    assert isinstance(sub.all(), abc.Iterator)
    assert [*sub.all()] == [*values] == [*sub.all(f'{__package__}++')] == [*sub.all(f'{__package__}**')]

    test = 'test'
    byname = [*sub.all(name=test)] 
    byname_n_mods = [*sub.all(name=test, module=[*mods])] 
    bypattern = [*sub.all(f'**:{test}')] 
    bypattern2 = [*sub.all(f'++:{test}')] 
    byregex = [*sub.all(re.compile(rf'^.+\:{test}$'))] 
    expected = [i for i in values if i.name == test]
    sep = '\n      - '
    print('\n', f'Name: {test!r}')
    print(f"  - expected -->", [v.qualname for v in expected], sep=sep)
    print(f"  - byname={test!r} -->", [v.qualname for v in byname], sep=sep)
    print(f"  - byname_n_mods={test!r} {[*mods]} -->", [v.qualname for v in byname_n_mods], sep=sep)
    print(f"  - bypattern={f'{test}:**'!r} -->", [v.qualname for v in bypattern], sep=sep)
    print(f"  - bypattern2={f'{test}:++'!r} -->", [v.qualname for v in bypattern2], sep=sep)
    print(f"  - byregex=r{f'^{test}:.*'!r} -->", [v.qualname for v in byregex], sep=sep)

    assert expected == byname == byname_n_mods == bypattern == bypattern2 == byregex

    byqualname_grouped = [*sub.all(*items, group=True)]
    expected_grouped = [tuple(it) for it in items.values()]
    assert byqualname_grouped == expected_grouped

    for test in mods:

        byname = [*sub.all(module=test)] 
        bypattern = [*sub.all(f'{test}:**')] 
        bypattern2 = [*sub.all(f'{test}:++')] 
        byregex = [*sub.all(re.compile(f'^{test}:.*'))] 
        expected = [i for i in values if i.module == test]

        print('\n', f'Module: {test!r}')
        print(f"  - expected -->", [v.qualname for v in expected], sep=sep)
        print(f"  - byname={test!r} -->", [v.qualname for v in byname], sep=sep)
        print(f"  - bypattern={f'{test}:**'!r} -->", [v.qualname for v in bypattern], sep=sep)
        print(f"  - bypattern2={f'{test}:++'!r} -->", [v.qualname for v in bypattern2], sep=sep)
        print(f"  - byregex=r{f'^{test}:.*'!r} -->", [v.qualname for v in byregex], sep=sep)

        assert expected == byname == bypattern == bypattern2 == byregex
        names = 'g0','c0'
        bynames = [*sub.all(module=test, name=names)]
        expected = [i for i in values if i.module == test and i.name in names]
        assert bynames == expected


    names = 'g0','c0'
    assert [*sub.all(*(f'**:{n}' for n in names))] == sorted((v for v in values if v.name in names), key=lambda v: names.index(v.name))



@xfail(raises=ValueError, strict=True)
@parametrize(['name', 'module'], [
    (list('abc'), list('abcde')),
    (list('abcde'), list('abc')),
])
def test_all_invalid(new: _T_FnNew, name, module):
    sub = new()
    print(f'{name=}, {module=}')
    [*sub.all(name=name, module=module)]



def test_find(new: _T_FnNew, cls, MockGroup: type[Group]):
    with patch.object(cls, 'all'):
        cls.all.return_value = vall = [MockGroup(),MockGroup()]
        sub = new()
        args, kwds = tuple('abc'), dict(name='n', module='m', group=True)
        res = sub.find(*args, **kwds)
        sub.all.assert_called_once_with(*args, **kwds)
        assert res is vall[0]