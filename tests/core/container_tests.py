import typing as t
import pytest



from collections.abc import Callable
from xdi._common import FrozenDict


from xdi.containers import Container
from xdi.providers import Provider, AbstractProviderRegistry


from ..abc import BaseTestCase


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize



_T = t.TypeVar('_T')
_T_Miss = t.TypeVar('_T_Miss')
_T_Ioc = t.TypeVar('_T_Ioc', bound=Container)

_T_FnNew = Callable[..., Container]


class ContainerTest(BaseTestCase[_T_Ioc]):

    type_: t.ClassVar[type[_T_Ioc]] = Container

    def test_basic(self, new: _T_FnNew):
        sub = new('test_ioc')
        str(sub)
        assert isinstance(sub, Container)
        assert isinstance(sub, FrozenDict)
        assert isinstance(sub, AbstractProviderRegistry)
        assert isinstance(sub.bases, tuple)

        assert sub
        assert sub.name == 'test_ioc'
        assert sub[_T] is None
        
    def test_compare(self, new: _T_FnNew):
        c1, c2 = new('c'), new('c')
        assert isinstance(hash(c1), int)
        assert c1 != c2 and not (c1 == c2) and c1.name == c2.name
      
    def test_immutable(self, new: _T_FnNew, immutable_attrs):
        self.assert_immutable(new(), immutable_attrs)

    def test_include(self, new: _T_FnNew):
        c1, c2, c3, c4 = new('c1'), new('c2'), new('c3'), new('c4')
        assert c1.extend(c3).extend(c2.extend(c4), c2) is c1
        assert c1.bases == (c3, c2)
        assert c2.bases == (c4,)
        assert c1.extends(c1) and c1.extends(c2) and c1.extends(c3) and c1.extends(c4)
        assert not (c2.extends(c1) or c2.extends(c3))

    def test_pro(self, new: _T_FnNew):
        c1, c2, c3, c4, c5, c6 = new('c1'), new('c2'), new('c3'), new('c4'), new('c5'), new('c6')
        c1.extend(c2.extend(c4.extend(c5, c6)))
        c1.extend(c3.extend(c5))
        pro = c1._evaluate_pro()
        assert isinstance(pro, tuple)
        print(*(f'{c}' for c in c1.pro), sep='\n  - ')
        assert pro == c1.pro
        assert pro == (c1, c2, c4, c3, c5, c6)

    @xfail(raises=TypeError, strict=True)
    def test_inconsistent_pro(self, new: _T_FnNew):
        c1, c2, c3= new('c1'), new('c2'), new('c3')
        c1.extend(c3, c2.extend(c3))
        c1.pro

    def test_setitem(self, new: _T_FnNew, mock_provider: Provider):
        sub = new()
        assert not _T in sub
        sub[_T] = mock_provider
        assert _T in sub
        assert sub[_T] is mock_provider
        mock_provider.container is sub
        mock_provider._setup.assert_called_once_with(sub)
    
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




