import pytest
import typing as t


from laza.di.injectors import MainInjector, LocalInjector
from laza.di.containers import IocContainer


@pytest.fixture()
def ioc():
    return IocContainer()


@pytest.fixture()
def main_injector():
    return MainInjector()


@pytest.fixture()
def local_injector(main_injector):
    return LocalInjector(main_injector)




@pytest.fixture()
def injector(main_injector):
    return main_injector



@pytest.fixture()
def scope(injector):
    with injector.make() as scp:
        yield scp

