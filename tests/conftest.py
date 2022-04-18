import asyncio
import operator
from unittest.mock import MagicMock, Mock, NonCallableMagicMock
import pytest
import typing as t
from xdi import is_injectable
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
def immutable_attrs(cls):
    return ()


@pytest.fixture
def value_factory_spec():
    return object

@pytest.fixture
def value_factory(value_factory_spec):
    return MagicMock(value_factory_spec, wraps=value_factory_spec)



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
def MockDependency():
    def make(abstract=None, scope=None, **kw):
        mk = MagicMock(Dependency)

        if not abstract is None:
            kw['abstract'] = abstract

        if not scope is None:
            kw['scope'] = scope
        
        kw.setdefault('is_async', False)

        for k,v in kw.items():
            setattr(mk, k, v)
        return mk

    return MagicMock(type[Dependency], wraps=make)




@pytest.fixture
def Mockinjector(MockScope):
    def make(spec=Injector, *, scope=None, parent=True, **kw):
        mi: Injector = NonCallableMagicMock(spec, **kw)
        mi.__bool__.return_value = True
        mi.scope = scope or MockScope()
        def mock_dep(k):
            if getattr(k, 'is_async', False):
                # mi = Mock()
                # def wrap(*a, **kw):
                #     return asyncio.sleep(0, mi)
                mk = MagicMock(asyncio.sleep)
            else:
                mk = MagicMock(t.Callable)
            return mk

        for k,v in kw.items():
            setattr(mi, k, v)

        deps = {}
        mi.__getitem__ = mi.find_local = Mock(wraps=lambda k: deps.get(k) or deps.setdefault(k, mock_dep(k)))
        mi.__setitem__ = Mock(wraps=lambda k, v: deps.__setitem__(k, v))

        return mi
    return MagicMock(type[Injector], wraps=make)




@pytest.fixture
def MockProvider(MockDependency):
    def make(spec=Provider, **kw):
        mi: Provider = NonCallableMagicMock(spec, **kw)
        deps = {}
        def mock_dep(a, s):
            if not (a, s) in deps:
                deps[a,s] = MockDependency(a, s, provider=mi)
            return deps[a,s]

        mi.resolve = MagicMock(wraps=mock_dep)
        mi.container = None
        mi.set_container = MagicMock(wraps=lambda c: (mi.container and mi) or setattr(mi, 'container', c) or mi)
        for k,v in kw.items():
            setattr(mi, k, v)

        return mi
    return MagicMock(type[Provider], wraps=make)



@pytest.fixture
def MockScope(MockContainer, MockDependency):
    def make(spec=Scope, *, parent=True, **kw):
        mi = NonCallableMagicMock(spec, **kw)
        mi.container = cm = MockContainer()
        mi.maps = dict.fromkeys((cm, MockContainer())).keys()
        mi.__contains__ = MagicMock(operator.__contains__, wraps=lambda k: deps.get(k) or is_injectable(k)) 
        
        deps = {}
        mi.__getitem__ = mi.find_local = Mock(wraps=lambda k: deps[k] if k in deps else deps.setdefault(k, MockDependency(abstract=k, scope=mi)))
        mi.__setitem__ = Mock(wraps=lambda k, v: deps.__setitem__(k, v))

        if parent:
            mi.parent = make(parent=parent-1) if parent is True else parent
            mi.find_remote = mi.parent.__getitem__

        for k,v in kw.items():
            setattr(mi, k, v)

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
def mock_injector(Mockinjector, mock_scope):
    return Mockinjector(scope=mock_scope)




