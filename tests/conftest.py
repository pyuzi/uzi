from collections import defaultdict
from functools import partial
import logging
from textwrap import wrap
from unicodedata import name
from unittest.mock import MagicMock, Mock, NonCallableMagicMock
import pytest
import typing as t
from xdi.providers import Provider

from xdi._dependency import Dependency

from xdi.test import TestContainer, TestInjectorContext, TestScope



@pytest.fixture()
def Container():
    return TestContainer


@pytest.fixture()
def container(Container):
    return Container()



@pytest.fixture()
def Scope():
    return partial(TestScope, injector_class=TestInjectorContext)


@pytest.fixture()
def scope(Scope, container):
    return Scope(container)



@pytest.fixture()
def ctx_manager(injector):
    return injector.exitstack


@pytest.fixture()
def context(injector):
    with injector.exitstack:
        yield injector


@pytest.fixture()
def injector(scope: TestScope):
    return scope.injector()
   



@pytest.fixture
def new_args():
    return ()

@pytest.fixture
def new_kwargs():
    return {}


@pytest.fixture
def new(cls, new_args, new_kwargs):
    logging.info(f'{new_args=}, {new_kwargs=}')
    return lambda *a, **kw: cls(*a, *new_args[len(a):], **{**new_kwargs, **kw})




@pytest.fixture
def MockContainer(Container):
    def make(spec=TestContainer, **kw):
        mi: Container = NonCallableMagicMock(spec, **kw)
        mi._dro_entries_.return_value = (mi,)
        mi.__bool__.return_value = True
        mi.__hash__.return_value = id(mi)
        mi.__getitem__.return_value = None
        return mi
    return MagicMock(type[Container], wraps=make)




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
    def make(spec=TestScope, *, parent=True, **kw):
        mi = NonCallableMagicMock(spec, **kw)
        mi.container = cm = MockContainer()
        mi.maps = dict.fromkeys((cm, MockContainer())).keys()
        mi.__contains__.return_value = True # Mock(wraps=lambda k: k in deps or k in mi.maps or (parent and k in mi.parent))
        def mock_dep(k):
            mk = Mock(Dependency)
            mk.scope = mi
            mk.provides = k
            return mk

        deps = {} # defaultdict(lambda: MagicMock(Dependency))
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




# @pytest.fixture
# def MockContainer(self):
#     x = 0
#     def make(name='mock', *a, **kw):
#         nonlocal x
#         x += 1
#         mi: Container = MagicMock(spec=Container, name=f'{name}')
#         mi._dro_entries_ = Mock(return_value=(mi,))
#         mi.__getitem__.return_value = None
#         mock = Mock(spec=type[Container], return_value=mi)
#         return mock(name, *a, **kw)
#     return make
