import pytest
import typing as t



@pytest.fixture()
def ioc():
    from laza.di.containers import IocContainer
    return IocContainer()


@pytest.fixture()
def main_scope():
    from laza.di.scopes import MainScope
    return MainScope()


@pytest.fixture()
def local_scope(main_scope):
    from laza.di.scopes import LocalScope
    return LocalScope(main_scope)




@pytest.fixture()
def scope(main_scope):
    return main_scope



@pytest.fixture()
def injector(scope):
    with scope.make() as inj:
        yield inj

