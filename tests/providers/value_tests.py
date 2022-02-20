import pytest

import typing as t



from laza.di.providers import Value as Provider


from .abc import ProviderTestCase


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_T = t.TypeVar('_T')

@pytest.fixture
def provider():
    return Provider(_T, object())


@pytest.fixture
def provided(provider: Provider):
    return lambda: provider.uses



class ValueProviderTests(ProviderTestCase):
    
    cls = Provider


    

