from functools import partial
import pytest
import typing as t


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
   

