import pytest
import typing as t


from laza.di.injectors import Injector, wire
from laza.di.test import TestContainer, TestInjector



@pytest.fixture()
def Container():
    return TestContainer


@pytest.fixture()
def container(Container):
    return Container()



@pytest.fixture()
def Injector():
    return TestInjector


@pytest.fixture()
def injector(Injector):
    return Injector()



@pytest.fixture()
def ctx_manager(injector: Injector):
    return wire(injector)


@pytest.fixture()
def context(ctx_manager):
    with ctx_manager as ctx:
        yield ctx

