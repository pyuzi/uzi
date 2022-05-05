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
from xdi.scopes import NullScope, Scope



from ..abc import BaseTestCase
from .. import assertions

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize



_T = t.TypeVar('_T')
_T_Scp = t.TypeVar('_T_Scp', bound=Scope)

_T_FnNew = Callable[..., Scope]

   
   
# class ScopeTest(BaseTestCase[_T_Scp]):

# type_: t.ClassVar[type[_T_Scp]] = Scope

@pytest.fixture
def new_args(MockContainer: type[Container]):
    return MockContainer(),

@pytest.fixture
def cls():
    return Scope



@pytest.fixture
def immutable_attrs(cls):
    return [a for a in dir(cls) if not (a[:2] == '__' == a[-2:] or ismethod(getattr(cls, a)))]


def test_basic(new: _T_FnNew, MockDependency):
    sub = new()
    assert isinstance(sub, Scope)
    assert isinstance(sub.container, Container)
    assert isinstance(sub.parent, NullScope)
    assert isinstance(sub.pros, Mapping)
    assert sub.container in sub.pros
    assert sub
    assert len(sub) == 0
    assert not sub.parent
    assert sub.level == 0
    str(sub)

def test_container(new: _T_FnNew, MockContainer: type[Container]):
    container = MockContainer()
    sub = new(container)
    assert container
    assert isinstance(container, Container)
    assert sub.container is container
    assert sub.name == container.name

def test_immutable(new: _T_FnNew, immutable_attrs):
    assertions.is_immutable(new(), immutable_attrs)
    
def test_compare(new: _T_FnNew, MockContainer: type[Container]):
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
        
def test_parent(new: _T_FnNew, MockContainer: type[Container]):
    sub = new(MockContainer(), None)
    assert not sub.parent
    assert isinstance(sub.parent, NullScope)
    assert sub.level == 0
    sub2 = new(MockContainer(), sub)
    assert sub2.parent is sub
    assert sub2.level == 1     

def test_parents(new: _T_FnNew, MockContainer: type[Container]):
    sub1 = new(MockContainer())
    sub2 = new(MockContainer(), sub1)
    sub3 = new(MockContainer(), sub2)
    sub4 = new(MockContainer(), sub3)

    assert sub4.level == 3
    
    it = sub4.parents()
    assert isinstance(it, Iterator)
    assert tuple(it) == (sub3, sub2, sub1)

@xfail(raises=ProError, strict=True)
def test_parent_with_same_container(new: _T_FnNew, MockContainer: type[Container]):
    c = MockContainer()
    new(c, new(c)) 

@xfail(raises=ProError, strict=True)
def test_parent_with_container(new: _T_FnNew, MockContainer: type[Container]):
    c1, c2 = (MockContainer() for i in range(2))
    c1.pro = c1, c2,
    c2.pro = c2,

    sub = new(c1)
    assert sub.container is c1
    new(c2, sub)
    
    
def test_find_provider(new: _T_FnNew, MockContainer: type[Container], MockProvider: type[Provider]):
    c0, c1, c2, c3 = (MockContainer() for i in range(4))
    
    c1.pro = (c1, c2, c3)

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

    key = sub.make_key(_T)

    assert base.find_provider(key) == sub.find_provider(key) == None

    c0._resolve.return_value = p0,
    c1._resolve.return_value = p1,
    c2._resolve.return_value = p2,
    c3._resolve.return_value = p3,

    assert p0 is base.find_provider(key)
    assert p1 is sub.find_provider(key)

    p1.is_default = True
    assert p2 is sub.find_provider(key)

    p2.is_default = True
    assert p3 is sub.find_provider(key)
    
    p3.is_default = True
    assert p1 is sub.find_provider(key)
    assert p0 is base.find_provider(key)
    

@xfail(raises=FinalProviderOverrideError, strict=True)
def test_overridden_final_find_provider(new: _T_FnNew, MockContainer: type[Container], MockProvider: type[Provider]):
    c0, c1, c2 = (MockContainer() for i in range(3))
    
    c0.pro = (c0, c1, c2)

    sub = new(c0)

    p0 = MockProvider(name='P0', is_final=False, is_default=False)
    p1 = MockProvider(name='P1', is_final=True, is_default=False)
    p2 = MockProvider(name='P2', is_final=False, is_default=False)

    key = sub.make_key(_T)

    c0._resolve.return_value = p0,
    c1._resolve.return_value = p1,
    c2._resolve.return_value = p2,

    sub.find_provider(key)


def test_getitem(new: _T_FnNew, MockContainer: type[Container], MockProvider: type[Provider]):
    ca, ca1, ca2, cb, cb1, cb2 = (MockContainer() for i in range(6))
    pro_a = ca, ca1, ca2
    pro_b = cb, cb1, cb2
    
    ca.pro = pro_a
    cb.pro = pro_b

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

    assert not(_Ta in sub_a or _Ta in sub_b)
    assert not(_Tb in sub_a or _Tb in sub_b)

    assert sub_a[_Ta] is sub_b[_Ta] is sub_a[_Ta] is sub_b[_Ta]
    assert not sub_a[_Tb]
    assert not(sub_a[_Tx] or sub_b[_Tx])
    assert sub_b[_Tb] == sub_b[_Tb] == sub_b[_Tb]

    print('', sub_a[_Tb], sub_a[_Ta],sub_b[_Tb], sub_b[_Ta],sub_b[_Tx], sep='\n  ---> ')
    print('', *sub_a.keys(), sep='\n   -=> ')
    print('', *sub_b.keys(), sep='\n   -=> ')

    assert _Ta in sub_a and _Ta in sub_b
    assert _Tb not in sub_a and _Tb in sub_b

    # assert len(sub_a) == 1
    # assert len(sub_b) == 2 
    
    pa0._resolve.assert_not_called()
    pb0._resolve.assert_not_called()

    pa1._resolve.assert_called_with(_Ta, sub_a)
    pb1._resolve.assert_called_once_with(_Tb, sub_b)

@xfail(raises=TypeError, strict=True)
def test_fail_invalid_getitem(new: _T_FnNew):
    new()[2345.6789]
    
def _test_find_local(new: _T_FnNew, mock_scope: Scope):
    mock_scope.__contains__.return_value = False
    sub = new(parent=mock_scope)
    dep = mock_scope[_T]
    assert isinstance(dep, Binding)
    assert sub.find_local(_T) is None
    assert sub[_T] is dep
    assert sub.find_local(_T) is None 

def _test_find_local_existing(new: _T_FnNew, mock_scope: Scope, mock_provider: Provider):
    mock_scope.__contains__.return_value = False
    sub = new(parent=mock_scope)
    sub.container.__getitem__.return_value = mock_provider
    dep = mock_provider._resolve(_T, sub)
    assert isinstance(dep, Binding)
    assert sub.find_local(_T) is dep
    assert sub[_T] is dep
    
def _test_find_remote(new: _T_FnNew, mock_scope: Scope, mock_provider: Provider):
    mock_scope.__contains__.return_value = False
    sub = new(parent=mock_scope)
    sub.container.__getitem__.return_value = mock_provider
    rdep = mock_scope[_T]

    assert isinstance(rdep, Binding)
    assert sub.find_remote(_T) is rdep

    ldep = mock_provider._resolve(_T, sub)
    assert isinstance(ldep, Binding)
    assert sub[_T] is ldep
    assert sub.find_remote(_T) is rdep



    
