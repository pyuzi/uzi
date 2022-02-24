import pytest

import typing as t



from laza.di.providers import InjectProvider as Provider

from laza.di.common import Inject
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
def provider():
    return Provider(Inject(_Tx, default=Inject(_Ta)))




@pytest.fixture
def provided(injectorcontext: Injector):
    return lambda: injectorcontext[_Ta]() # injector.resolver[_Ta].uses




class InjectProviderTests(ProviderTestCase):
    
    cls = Provider


