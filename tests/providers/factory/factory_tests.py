import asyncio
from collections import abc
import pytest

import typing as t
from xdi import Dep



from xdi.providers import Factory as Provider


from .abc import ProviderTestCase


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize

_T_NewPro =  abc.Callable[..., Provider]



class FactoryProviderTests(ProviderTestCase[Provider]):
   
    def test_is_async(self, new: _T_NewPro):
        subject = new()
        subject.asynchronous()
        assert subject.is_async
        subject.asynchronous(False)
        assert not subject.is_async
        subject.asynchronous()
        assert subject.is_async
    
