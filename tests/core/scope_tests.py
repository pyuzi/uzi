import typing as t
import attr
import pytest

from unittest.mock import  MagicMock, Mock

from collections.abc import Callable, Iterator, Set, MutableSet
from xdi._common import frozendict


from xdi.containers import Container
from xdi.providers import Provider
from xdi._dependency import Dependency
from xdi.scopes import EmptyScopeError, NullScope, Scope



from ..abc import BaseTestCase

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_T = t.TypeVar('_T')
_T_Scp = t.TypeVar('_T_Scp', bound=Scope)

_T_FnNew = Callable[..., _T_Scp]

   
   
class ScopeTest(BaseTestCase[_T_Scp]):

    type_: t.ClassVar[type[_T_Scp]] = Scope

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
    
    def test_immutable(self, new: _T_FnNew, immutable_attrs):
        self.assert_immutable(new(), immutable_attrs)
        
    def test_compare(self, new: _T_FnNew, MockContainer: type[Container]):
        c1 = MockContainer()
        sub1, sub2 = new(c1), new(c1),
        assert sub1.container is c1 is sub2.container
        assert sub1 == sub2 and not (sub1 != sub2)
        assert sub1 != c1 and not(sub1 == c1)
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
    
    @xfail(raises=EmptyScopeError, strict=True)
    def test_parent_with_same_container(self, new: _T_FnNew, MockContainer: type[Container]):
        c = MockContainer()
        new(c, new(c)) 

    @xfail(raises=EmptyScopeError, strict=True)
    def test_parent_with_container(self, new: _T_FnNew, MockContainer: type[Container]):
        c1, c2 = (MockContainer() for i in range(2))
        c1._dro_entries_.return_value = c1, c2,
        c2._dro_entries_.return_value = c2,

        sub = new(c1)
        assert sub.container is c1
        new(c2, sub)

    def test_maps(self, new: _T_FnNew, MockContainer: type[Container]):
        c1, c2, c3, c4, c5 = (MockContainer() for i in range(5))
        dro = c1, c2, c3, c5, c4, c3, c5
        c1._dro_entries_.return_value = dro
        sub = new(c1)
        assert sub.container is c1
        assert sub.maps & {*dro} == {*dro}
        assert all(c in sub for c in {*dro})

    def test_maps_with_parents(self, new: _T_FnNew, MockContainer: type[Container]):
        ca, c2, c3, cb, c5, c6 = (MockContainer() for i in range(6))
        dro_a = ca, c2, c3, c5,
        dro_b = cb, c3, c5, c6,

        ca._dro_entries_.return_value = dro_a
        cb._dro_entries_.return_value = dro_b

        sub_a = new(ca)
        sub_b = new(cb, sub_a)
        assert sub_a.maps & {*dro_a} == {*dro_a}
        assert sub_b.maps & {cb, c6} == {cb, c6}
        assert all(c in sub_a for c in {*dro_a})
        assert all(c in sub_b for c in {*dro_a, *dro_b})
        assert all(not c in sub_a for c in {*dro_b} - {*dro_a})
     
    def test_resolve_providers(self, new: _T_FnNew, MockContainer: type[Container], MockProvider: type[Provider]):
        c0, c1, c2, c3 = (MockContainer() for i in range(4))
        
        c1._dro_entries_.return_value = (c1, c2, c3)

        base = new(c0)
        sub = new(c1, base)

        p0 = MockProvider(name='P0')
        p0.is_default = False

        p1 = MockProvider(name='P1')
        p1.is_default = False

        p2 = MockProvider(name='P2')
        p2.is_default = False

        p3 = MockProvider(name='P3')
        p3.is_default = False

        assert base.resolve_providers(_T) == sub.resolve_providers(_T) == []

        c0.__getitem__.return_value = p0
        c1.__getitem__.return_value = p1
        c2.__getitem__.return_value = p2
        c3.__getitem__.return_value = p3

        assert [p0] == base.resolve_providers(_T)
        assert [p1, p2, p3] == sub.resolve_providers(_T)

        p1.is_default = True
        assert [p2, p3, p1] == sub.resolve_providers(_T)

        p2.is_default = True
        assert [p3, p1, p2] == sub.resolve_providers(_T)
        
        p3.is_default = True
        assert [p1, p2, p3] == sub.resolve_providers(_T)

        assert [p0] == base.resolve_providers(_T)

    def test_getitem(self, new: _T_FnNew, MockContainer: type[Container], MockProvider: type[Provider]):
        ca, ca1, ca2, cb, cb1, cb2 = (MockContainer() for i in range(6))
        dro_a = ca, ca1, ca2
        dro_b = cb, cb1, cb2
        
        ca._dro_entries_.return_value = dro_a
        cb._dro_entries_.return_value = dro_b

        fn_compose = lambda *a, **kw: object()

        sub_a = new(ca)
        sub_b = new(cb, sub_a)

        pa0 = MockProvider(name='PA0')
        pa0.is_default = True

        pa1 = MockProvider(name='PA1')
        pa1.is_default = False

        pb0 = MockProvider(name='PB0')
        pb0.is_default = True

        pb1 = MockProvider(name='PB1')
        pb1.is_default = False

        _Ta, _Tb, _Tx = t.TypeVar('_Ta'), t.TypeVar('_Tb'), t.TypeVar('_Tx'), 

        ca1.__getitem__ = Mock(wraps=lambda k: pa0 if k is _Ta else None )
        ca2.__getitem__ = Mock(wraps=lambda k: pa1 if k is _Ta else None )
        cb1.__getitem__ = Mock(wraps=lambda k: pb0 if k is _Tb else None )
        cb2.__getitem__ = Mock(wraps=lambda k: pb1 if k is _Tb else None )

        assert [pa1, pa0] == sub_a.resolve_providers(_Ta)
        assert [pb1, pb0] == sub_b.resolve_providers(_Tb)

        assert [] == sub_a.resolve_providers(_Tb)
        assert [] == sub_b.resolve_providers(_Ta)

        assert not(_Ta in sub_a or _Ta in sub_b)
        assert not(_Tb in sub_a or _Tb in sub_b)

        assert sub_a[_Ta] is sub_b[_Ta] is sub_a[_Ta] is sub_b[_Ta]
        assert not sub_a[_Tb]
        assert not(sub_a[_Tx] or sub_b[_Tx])
        assert sub_b[_Tb] == sub_b[_Tb] == sub_b[_Tb]

        assert _Ta in sub_a and _Ta in sub_b
        assert _Tb not in sub_a and _Tb in sub_b

        assert len(sub_a) == 1
        assert len(sub_b) == 2 
        
        pa0.resolve.assert_not_called()
        pb0.resolve.assert_not_called()
        pa1.resolve.assert_called_once_with(_Ta, sub_a)
        pb1.resolve.assert_called_once_with(_Tb, sub_b)
       
    def test_find_local(self, new: _T_FnNew, mock_scope: Scope):
        mock_scope.__contains__.return_value = False
        sub = new(parent=mock_scope)
        dep = mock_scope[_T]
        assert isinstance(dep, Dependency)
        assert sub.find_local(_T) is None
        assert sub[_T] is dep
        assert sub.find_local(_T) is None 

    def test_find_local_existing(self, new: _T_FnNew, mock_scope: Scope, mock_provider: Provider):
        mock_scope.__contains__.return_value = False
        sub = new(parent=mock_scope)
        sub.container.__getitem__.return_value = mock_provider
        dep = mock_provider.resolve(_T, sub)
        assert isinstance(dep, Dependency)
        assert sub.find_local(_T) is dep
        assert sub[_T] is dep
       
    def test_find_remote(self, new: _T_FnNew, mock_scope: Scope, mock_provider: Provider):
        mock_scope.__contains__.return_value = False
        sub = new(parent=mock_scope)
        sub.container.__getitem__.return_value = mock_provider
        rdep = mock_scope[_T]

        assert isinstance(rdep, Dependency)
        assert sub.find_remote(_T) is rdep

        ldep = mock_provider.resolve(_T, sub)
        assert isinstance(ldep, Dependency)
        assert sub[_T] is ldep
        assert sub.find_remote(_T) is rdep


   
        
    