import pytest

import typing as t



from laza.di.providers import UnionProvider as Provider

from laza.di.injectors import Injector
 

from .abc import ProviderTestCase


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_T = t.TypeVar('_T')

@pytest.fixture
def provider(injector: Injector):
    injector.value(_T, f'VALUE FOR [{_T!r}]!')
    return Provider(t.Union[_T, int])




@pytest.fixture
def provided(injectorcontext):
    return injectorcontext[_T]



class UnionProviderTests(ProviderTestCase):
    
    cls = Provider


