from os import name
from types import GenericAlias, new_class
import typing as t
import attr
import pytest


from unittest.mock import  Mock

from collections.abc import Callable, Iterator, Set, MutableSet, Iterable
from xdi._common.collections import frozendict


from xdi.containers import Container
from xdi.providers import Provider
from xdi.providers.util import ProviderRegistry


from .abc import BaseTestCase


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_T = t.TypeVar('_T')
_T_Ioc = t.TypeVar('_T_Ioc', bound=Container)

_T_FnNew = Callable[..., _T_Ioc]


class ContainerTest(BaseTestCase[_T_Ioc]):

    type_: t.ClassVar[type[_T_Ioc]] = Container

    def test_basic(self, new: _T_FnNew):
        sub = new('test_ioc')
        str(sub)
        assert isinstance(sub, Container)
        assert isinstance(sub, frozendict)
        assert isinstance(sub, ProviderRegistry)
        assert isinstance(sub.included, Set)
        assert not isinstance(sub.included, MutableSet)

        assert sub.name == 'test_ioc'
        assert sub
        assert len(sub) == 0
        assert isinstance(sub[_T], Iterable)
        
    def test_compare(self, new: _T_FnNew):
        c1, c2 = new('c'), new('c')
        assert isinstance(hash(c1), int)
        assert c1 != c2 and not (c1 == c2) and c1.name == c2.name
        assert c1._included == c1._included and c1.keys() == c2.keys()
      
    def test_immutable(self, new: _T_FnNew):
        sub = new()
        for atr in attr.fields(sub.__class__):
            try:
                sub.__setattr__(atr.name, getattr(sub, atr.name, None))
            except AttributeError:
                continue
            else:
                raise AssertionError(f"mutable: {atr.name!r} -> {sub}")

    def test_include(self, new: _T_FnNew):
        c1, c2, c3, c4 = new('c1'), new('c2'), new('c3'), new('c4')
        assert c1.include(c3).include(c2.include(c4), c2) is c1
        assert c1.included == {c3, c2}
        assert c2.included == {c4,}
        assert c1.includes(c1) and c1.includes(c2) and c1.includes(c3) and c1.includes(c4)
        assert not (c2.includes(c1) or c2.includes(c3))

    def test_dro_entries_basic(self, new: _T_FnNew):
        c1, c2, c3, c4, c5, c6 = new('c1'), new('c2'), new('c3'), new('c4'), new('c5'), new('c6')
        c1.include(c2.include(c4.include(c5, c6)))
        c1.include(c3.include(c5))
        it = c1._dro_entries_()
        assert isinstance(it, Iterator)
        edges = (c1,c1), (c1, c3), (c3, c5), (c1, c2), (c2, c4), (c4, c6), (c4, c5),
        assert tuple(it) == edges

    def test_dro_entries(self, new: _T_FnNew):
        def make(p: Container, n=3, lvl=0, depth=4):
            if lvl < depth:
                for x in range(1, int(n)+1):
                    nm = f'{p.name}/{x:02d}'
                    c = new(nm)
                    p.include(c)
                    print('   '*lvl, '-', c)
                    yield p, c
                    yield from make(c, n-.5, lvl+1, depth)
        c = new('C')
        ls = *make(c),
        
        # print('', *ls, sep='\n --> ')
        # print('', *c._dro_entries_(), sep='\n --> ')

        def dro(c: Container, *incs):
            for inc in c.included:
                yield from dro(inc, inc)
                # yield inc
            else:
                yield from incs[::-1]
        
        def dro(c: Container):
            yield c
            for inc in reversed(c.included):
                yield from dro(inc)

        it = *c.included,
        # it[1].include(it[2])

        print('', *dro(c), sep='\n --> ')

        c1, c2, c3, c4, c5, c6 = new('c1'), new('c2'), new('c3'), new('c4'), new('c5'), new('c6')
        c1.include(c2.include(c4.include(c5, c6)))
        c1.include(c3.include(c5))
        it = c1._dro_entries_()
        assert isinstance(it, Iterator)
        assert tuple(it) == ((c4, c5), (c4, c6), (c2, c4), (c1, c2), (c3, c5), (c1, c3), (c1, c1))

    def test_setitem(self, new: _T_FnNew):
        pro = Mock(spec=Provider)
        pro.set_container = Mock(return_value=pro)
        sub = new()

        assert isinstance(pro, Provider)
        assert _T not in sub
        sub[_T] = pro
        assert _T in sub
        assert tuple(sub[_T]) == (pro,)

        pro.set_container.assert_called_once_with(sub)
    
    
        