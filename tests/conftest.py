from functools import partial
from unittest.mock import Mock
import pytest
import typing as t
from xdi.providers import Provider


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
    return lambda *a, **kw: cls(*a, *new_args[len(a):], **{**new_kwargs, **kw})
