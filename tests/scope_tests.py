from itertools import chain
from os import sep
import typing as t
import attr
import pytest
import networkx as nx

from unittest.mock import  MagicMock, Mock

from collections.abc import Callable, Iterator, Set, MutableSet
from xdi._common import frozendict


from xdi.containers import Container
from xdi.providers import Provider
from xdi.scopes import NullScope, Scope



from .abc import BaseTestCase

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_T = t.TypeVar('_T')
_T_Scp = t.TypeVar('_T_Scp', bound=Scope)

_T_FnNew = Callable[..., _T_Scp]

        


class NullScopeTests(BaseTestCase[NullScope]):

    type_: t.ClassVar[type[_T_Scp]] = NullScope

    def test_basic(self, new: _T_FnNew):
        sub = new()
        assert isinstance(sub, NullScope)
        assert isinstance(sub, frozendict)
        assert isinstance(sub.maps, Set)
        assert not isinstance(sub.maps, MutableSet)
        assert sub.parent is None
        assert sub.level == -1
        assert not sub
        assert not sub.container
        assert not sub.maps
        str(sub)
        
    def test_compare(self, new: _T_FnNew):
        sub = new()
        assert sub == NullScope()
        assert not sub != NullScope()
        assert not sub is NullScope()
        assert hash(sub) == hash(NullScope())

    def test_is_blank(self, new: _T_FnNew):
        sub = new()
        assert len(sub) == 0
        assert sub[_T] is None
        assert not _T in sub

    def test_immutable(self, new: _T_FnNew):
        sub = new()
        for atr in attr.fields(sub.__class__):
            try:
                sub.__setattr__(atr.name, getattr(sub, atr.name, None))
            except AttributeError:
                continue
            else:
                raise AssertionError(f"mutable: {atr.name!r} -> {sub}")
        


class ScopeTest(BaseTestCase[_T_Scp]):

    type_: t.ClassVar[type[_T_Scp]] = Scope

    @pytest.fixture
    def MockContainer(self):
        x = 0
        def make(name='mock', *a, **kw):
            nonlocal x
            x += 1
            mi: Container = MagicMock(spec=Container, name=f'{name}')
            mi._dro_entries_ = Mock(return_value=(mi,))
            mi.__getitem__.return_value = None
            mock = Mock(spec=type[Container], return_value=mi)
            return mock(name, *a, **kw)
        return make

    @pytest.fixture
    def new_args(self, MockContainer: type[Container]):
        return MockContainer(),

    def test_basic(self, new: _T_FnNew):
        sub = new()
        assert isinstance(sub, Scope)
        assert isinstance(sub, frozendict)
        assert isinstance(sub.container, Container)
        assert isinstance(sub.parent, NullScope)
        assert isinstance(sub.maps, Set)
        assert not isinstance(sub.maps, MutableSet)
        assert sub.container in sub.maps
        assert sub
        assert len(sub) == 0
        assert not sub.parent
        assert sub.level == 0
        str(sub)
    
    def test_container(self, new: _T_FnNew, MockContainer: type[Container]):
        container = MockContainer()
        sub = new(container)
        assert container
        assert isinstance(container, Container)
        assert sub.container is container
        assert sub.name == container.name
    
    def test_immutable(self, new: _T_FnNew):
        sub = new()
        for atr in attr.fields(sub.__class__):
            try:
                sub.__setattr__(atr.name, getattr(sub, atr.name, None))
            except AttributeError:
                continue
            else:
                raise AssertionError(f"mutable: {atr.name!r} -> {sub}")
        
    def test_compare(self, new: _T_FnNew, container, MockContainer: type[Container]):
        sub1, sub2 = new(container), new(container),
        assert sub1.container is container is sub2.container
        assert sub1 == sub2 and not (sub1 != sub2)
        assert sub1 != container and not(sub1 == container)
        assert hash(sub1) == hash(sub2)

        c2 = MockContainer()
        sub11, sub22, sub3 = new(c2, sub1), new(c2, sub2), new(MockContainer(), sub2)
        assert sub11 == sub22
        assert sub11 != sub3 
        assert sub22 != sub3 
           
    def test_parent(self, new: _T_FnNew, MockContainer: type[Container]):
        sub = new(MockContainer())
        assert not sub.parent
        assert sub.level == 0
        sub2 = new(MockContainer(), sub)
        assert sub2.parent is sub
        assert sub2.level == 1     

    def test_parents(self, new: _T_FnNew, MockContainer: type[Container]):
        sub1 = new(MockContainer())
        sub2 = new(MockContainer(), sub1)
        sub3 = new(MockContainer(), sub2)
        sub4 = new(MockContainer(), sub3)

        assert sub4.level == 3
        
        it = sub4.parents()
        assert isinstance(it, Iterator)
        assert tuple(it) == (sub3, sub2, sub1)
    
    @xfail(raises=RuntimeError, strict=True)
    def test_parent_with_same_container(self, new: _T_FnNew, MockContainer: type[Container]):
        c = MockContainer()
        new(c, new(c)) 

    @xfail(raises=RuntimeError, strict=True)
    def test_parent_with_container(self, new: _T_FnNew, MockContainer: type[Container]):
        c1, c2 = (MockContainer(f'ioc{i:02d}') for i in range(2))
        c1._dro_entries_.return_value = c1, c2,
        c2._dro_entries_.return_value = c2,

        sub = new(c1)
        assert sub.maps == {c1, c2}
        assert sub.container is c1
        new(c2, sub)

    def test_maps(self, new: _T_FnNew, MockContainer: type[Container]):
        c1, c2, c3, c4, c5 = (MockContainer(f'ioc{i:02d}') for i in range(5))
        dro = c1, c2, c3, c5, c4, c3, c5
        c1._dro_entries_.return_value = dro
        sub = new(c1)
        assert sub.container is c1
        assert sub.maps == {*dro}
        assert tuple(sub.maps) ==  dro[:-2]
        assert all(c in sub for c in {*dro})

    def test_maps_with_parents(self, new: _T_FnNew, MockContainer: type[Container]):
        ca, c2, c3, cb, c5, c6 = (MockContainer(f'ioc{i:02d}') for i in range(6))
        dro_a = ca, c2, c3, c5,
        dro_b = cb, c3, c5, c6,

        ca._dro_entries_.return_value = dro_a
        cb._dro_entries_.return_value = dro_b

        sub_a = new(ca)
        sub_b = new(cb, sub_a)
        assert sub_a.maps == {*dro_a}
        assert sub_b.maps == {cb, c6}
        assert all(c in sub_a for c in {*dro_a})
        assert all(c in sub_b for c in {*dro_a, *dro_b})
        assert all(not c in sub_a for c in {*dro_b} - {*dro_a})
        
    def test_resolve_provider(self, new: _T_FnNew, MockContainer: type[Container]):
        c0, c1, c2, c3 = (MockContainer(f'ioc{i:02d}') for i in range(4))
        
        c1._dro_entries_.return_value = (c1, c2, c3)

        base = new(c0)
        sub = new(c1, base)

        p0 = Mock(Provider, name='P0')
        p0.is_default = MagicMock(False)
        p0.is_default.__bool__ = Mock(return_value=False)
        p1 = Mock(Provider, name='P1')
        p1.is_default = False

        p2 = Mock(Provider, name='P2')
        p2.is_default = False

        p3 = Mock(Provider, name='P3')
        p3.is_default = False

        assert base.resolve_provider(_T) is sub.resolve_provider(_T) is None

        c0.__getitem__.return_value = p0
        c1.__getitem__.return_value = p1
        c2.__getitem__.return_value = p2
        c3.__getitem__.return_value = p3

        assert p0 is base.resolve_provider(_T)
        assert p1 is sub.resolve_provider(_T)

        p1.is_default = True
        assert p2 is sub.resolve_provider(_T)

        p2.is_default = True
        assert p3 is sub.resolve_provider(_T)
        
        p3.is_default = True
        assert p1 is sub.resolve_provider(_T)

        assert p0 is base.resolve_provider(_T)
        
        c0.__getitem__.assert_called_with(_T)
        c1.__getitem__.assert_called_with(_T)
        c2.__getitem__.assert_called_with(_T)
        c3.__getitem__.assert_called_with(_T)

    def test_getitem(self, new: _T_FnNew, MockContainer: type[Container]):
        ca, ca1, ca2, cb, cb1, cb2 = (MockContainer(f'ioc{i:02d}') for i in range(6))
        dro_a = ca, ca1, ca2
        dro_b = cb, cb1, cb2
        
        ca._dro_entries_.return_value = dro_a
        cb._dro_entries_.return_value = dro_b

        sub_a = new(ca)
        sub_b = new(cb, sub_a)

        pa0 = Mock(spec=Provider, name='PA0')
        pa0.is_default = True

        fn_compose = lambda *a, **kw: object()

        pa1 = Mock(spec=Provider, name='PA1')
        pa1.compose = Mock(wraps=fn_compose)
        pa1.is_default = False

        pb0 = Mock(spec=Provider, name='PB0')
        pb0.is_default = True

        pb1 = Mock(spec=Provider, name='PB1')
        pb1.compose = Mock(wraps=fn_compose)
        pb1.is_default = False

        _Ta, _Tb, _Tx = t.TypeVar('_Ta'), t.TypeVar('_Tb'), t.TypeVar('_Tx'), 

        ca1.__getitem__ = Mock(wraps=lambda k: pa0 if k is _Ta else None )
        ca2.__getitem__ = Mock(wraps=lambda k: pa1 if k is _Ta else None )
        cb1.__getitem__ = Mock(wraps=lambda k: pb0 if k is _Tb else None )
        cb2.__getitem__ = Mock(wraps=lambda k: pb1 if k is _Tb else None )

        assert pa1 is sub_a.resolve_provider(_Ta)
        assert pb1 is sub_b.resolve_provider(_Tb)

        assert None is sub_a.resolve_provider(_Tb)
        assert None is sub_b.resolve_provider(_Ta)

        assert not(_Ta in sub_a or _Ta in sub_b)
        assert not(_Tb in sub_a or _Tb in sub_b)

        assert sub_a[_Ta] is sub_b[_Ta] is sub_a[_Ta] is sub_b[_Ta]
        assert sub_a[_Tb] is None
        assert sub_a[_Tx] is sub_b[_Tx] is None
        assert sub_b[_Tb] is sub_b[_Tb] is sub_b[_Tb]

        assert _Ta in sub_a and _Ta in sub_b
        assert _Tb not in sub_a and _Tb in sub_b

        assert len(sub_a) == 1
        assert len(sub_b) == 2 

        pa1.compose.assert_called_once_with(sub_a, _Ta)
        pb1.compose.assert_called_with(sub_b, _Tb)

       
       
   
        
    