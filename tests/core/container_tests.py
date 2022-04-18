import typing as t
import attr
import pytest



from collections.abc import Callable, Set, MutableSet, Iterable
from xdi._common import frozendict


from xdi.containers import Container
from xdi.providers import Provider, AbstractProviderRegistry


from ..abc import BaseTestCase


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize



_T = t.TypeVar('_T')
_T_Miss = t.TypeVar('_T_Miss')
_T_Ioc = t.TypeVar('_T_Ioc', bound=Container)

_T_FnNew = Callable[..., _T_Ioc]


class ContainerTest(BaseTestCase[_T_Ioc]):

    type_: t.ClassVar[type[_T_Ioc]] = Container

    def test_basic(self, new: _T_FnNew):
        sub = new('test_ioc')
        str(sub)
        assert isinstance(sub, Container)
        assert isinstance(sub, frozendict)
        assert isinstance(sub, AbstractProviderRegistry)
        assert isinstance(sub.included, Set)
        assert not isinstance(sub.included, MutableSet)

        assert sub
        assert sub.name == 'test_ioc'
        assert sub[_T] is None
        assert len(sub) == 0
        
    def test_compare(self, new: _T_FnNew):
        c1, c2 = new('c'), new('c')
        assert isinstance(hash(c1), int)
        assert c1 != c2 and not (c1 == c2) and c1.name == c2.name
        assert c1._included == c1._included and c1.keys() == c2.keys()
      
    def test_immutable(self, new: _T_FnNew, immutable_attrs):
        self.assert_immutable(new(), immutable_attrs)

    def test_include(self, new: _T_FnNew):
        c1, c2, c3, c4 = new('c1'), new('c2'), new('c3'), new('c4')
        assert c1.include(c3).include(c2.include(c4), c2) is c1
        assert c1.included == {c3, c2}
        assert c2.included == {c4,}
        assert c1.includes(c1) and c1.includes(c2) and c1.includes(c3) and c1.includes(c4)
        assert not (c2.includes(c1) or c2.includes(c3))

    def test_dro_entries(self, new: _T_FnNew):
        c1, c2, c3, c4, c5, c6 = new('c1'), new('c2'), new('c3'), new('c4'), new('c5'), new('c6')
        c1.include(c2.include(c4.include(c5, c6)))
        c1.include(c3.include(c5))
        it = c1._dro_entries_()
        assert isinstance(it, Iterable)
        dro = c1, c3, c5, c2, c4, c6, c5,

        assert tuple(it) == dro

    def test_setitem(self, new: _T_FnNew, mock_provider: Provider):
        sub = new()
        assert not _T in sub
        sub[_T] = mock_provider
        assert _T in sub
        assert sub[_T] is mock_provider
        mock_provider.container is sub
        mock_provider.set_container.assert_called_once_with(sub)
    
    def test_getitem(self, new: _T_FnNew, mock_provider: Provider):
        sub = new()
        sub[_T] = mock_provider
        assert sub[_T] is mock_provider
        assert sub[_T_Miss] is None

    def test_missing(self, new: _T_FnNew, MockProvider: type[Provider]):
        sub = new()
        pro1, pro2, pro3 = (MockProvider() for _ in range(3))
        pro3.container = new()
        sub[_T] = pro1
        assert sub[_T] is pro1
        assert sub[_T_Miss] is None
        assert sub[pro1] is pro1
        assert sub[pro2] is pro2
        assert sub[pro3] is None

    
        