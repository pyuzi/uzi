import pytest

import typing as t



from laza.di.providers import AnnotatedProvider as Provider

from laza.di.injectors import Injector
 

from .abc import ProviderTestCase


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_T = t.TypeVar('_T')
_Ta = t.TypeVar('_Ta')
_Tb = t.TypeVar('_Tb')
_Tc = t.TypeVar('_Tc')
_Tx = t.TypeVar('_Tx')


@pytest.fixture
def injector(injector: Injector):
    for t_ in (_Ta, _Tb, _Tc):
        injector.value(t_, f'VALUE FOR [{t_!r}]!')
    return injector


@pytest.fixture
def provider(injector: Injector):
    injector.value(_T, f'VALUE FOR [{_T!r}]!')
    return Provider(t.Annotated[t.Any, _Ta])



@pytest.fixture
def provided(injectorcontext):
    return injectorcontext[_Ta]






class AnnotatedProviderTests(ProviderTestCase):
    
    cls = Provider


