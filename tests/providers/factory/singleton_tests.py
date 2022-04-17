import asyncio
import pytest

import typing as t



from xdi.providers import Singleton as Provider


from ..abc import _T_NewPro, ProviderTestCase


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_T_NewPro =  _T_NewPro[Provider]


class SingletonProviderTests(ProviderTestCase[Provider]):
    ...
    
    