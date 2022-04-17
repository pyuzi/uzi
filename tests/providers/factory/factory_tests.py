import asyncio
import pytest

import typing as t
from xdi import Dep



from xdi.providers import Factory as Provider


from .abc import ProviderTestCase, _T_NewPro


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize

_T_NewPro =  _T_NewPro[Provider]



class FactoryProviderTests(ProviderTestCase[Provider]):
    ...
   