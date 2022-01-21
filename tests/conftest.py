import pytest
import typing as t



@pytest.fixture()
def ioc():
    from laza.di import IocContainer
    return IocContainer()

