from unittest.mock import MagicMock, Mock, NonCallableMagicMock
import pytest
import typing as t
from xdi.containers import Container
from xdi.injectors import Injector
from xdi.providers import Provider

from xdi._dependency import Dependency
from xdi.scopes import Scope






@pytest.fixture
def new_args():
    return ()

@pytest.fixture
def new_kwargs():
    return {}


@pytest.fixture
def new(cls, new_args, new_kwargs):
    return lambda *a, **kw: cls(*a, *new_args[len(a):], **{**new_kwargs, **kw})




@pytest.fixture
def MockContainer():
    def make(spec=Container, **kw):
        mi: Container = NonCallableMagicMock(spec, **kw)
        mi._dro_entries_.return_value = (mi,)
        mi.__bool__.return_value = True
        mi.__hash__.return_value = id(mi)
        mi.__getitem__.return_value = None
        return mi
    return MagicMock(type[Container], wraps=make)




@pytest.fixture
def Mockinjector(MockScope):
    def make(spec=Injector, *, scope=None, parent=True, **kw):
        mi: Injector = NonCallableMagicMock(spec, **kw)
        mi.__bool__.return_value = True
        mi.scope = scope or MockScope()
        # mi.__getitem__.return_value = None
        
        return mi
    return MagicMock(type[Injector], wraps=make)




@pytest.fixture
def MockProvider():
    def make(spec=Provider, **kw):
        mi: Provider = NonCallableMagicMock(spec, **kw)
        deps = {}
        def mock_dep(a, s):
            if mk := deps.get((a,s)):
                return mk
            deps[a,s] = mk = Mock(Dependency)
            mk.scope = s
            mk.provides = a
            mk.provider = mi
            return mk

        mi.resolve = MagicMock(wraps=mock_dep)
        return mi
    return MagicMock(type[Provider], wraps=make)



@pytest.fixture
def MockScope(MockContainer):
    def make(spec=Scope, *, parent=True, **kw):
        mi = NonCallableMagicMock(spec, **kw)
        mi.container = cm = MockContainer()
        mi.maps = dict.fromkeys((cm, MockContainer())).keys()
        mi.__contains__.return_value = True 
        def mock_dep(k):
            mk = Mock(Dependency)
            mk.scope = mi
            mk.provides = k
            return mk

        deps = {}
        mi.__getitem__ = mi.find_local = Mock(wraps=lambda k: deps.get(k) or deps.setdefault(k, mock_dep(k)))
        mi.__setitem__ = Mock(wraps=lambda k, v: deps.__setitem__(k, v))
        if parent:
            mi.parent = make(parent=parent-1, **kw)
            mi.find_remote = mi.parent.__getitem__
        return mi
    return MagicMock(type[Container], wraps=make)


@pytest.fixture
def mock_container(MockContainer):
    return MockContainer()


@pytest.fixture
def mock_scope(MockScope):
    return MockScope()


@pytest.fixture
def mock_provider(MockProvider):
    return MockProvider()



@pytest.fixture
def mock_injector(Mockinjector):
    return Mockinjector()




