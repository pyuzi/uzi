import asyncio
import pytest

import typing as t


from uzi.providers import Singleton as Provider


from ..abc import _T_NewPro, ProviderTestCase


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_T_NewPro = _T_NewPro[Provider]


class SingletonProviderTests(ProviderTestCase[Provider]):
    def test_is_thread_safe(self, new: _T_NewPro):
        subject = new()
        subject.thread_safe()
        assert subject.is_thread_safe
        subject.thread_safe(False)
        assert not subject.is_thread_safe
        subject.thread_safe()
        assert subject.is_thread_safe
