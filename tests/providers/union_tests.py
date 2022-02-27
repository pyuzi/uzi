import pytest

import typing as t



from laza.di.providers import UnionProvider as Provider, Factory

from laza.di.injectors import Injector

from libs.di.laza.di import injectors
 

from .abc import ProviderTestCase


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_T = t.TypeVar('_T')
_Ta = t.TypeVar('_Ta')



class UnionProviderTests(ProviderTestCase):
    
    @pytest.fixture
    def provider(self):
        return Provider(t.Union[_T, _Ta])

    @pytest.fixture
    def injector(self, injector: Injector, value_setter):
        injector.register(Factory(value_setter).provide(_Ta))
        return injector

