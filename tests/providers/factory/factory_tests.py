import asyncio
from collections import abc
from functools import partial
from inspect import Signature
import pytest

import typing as t
from uzi import Dep



from uzi.providers import Factory as Provider


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
    

    def test_get_signature(self, new: _T_NewPro):
        subject = new()
        subject.use(partial(subject.concrete))
        sig = subject.get_signature()
        assert isinstance(sig, Signature)