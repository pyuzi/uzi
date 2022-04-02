import pytest

import typing as t



from xdi.providers import Value as Provider


from .abc import ProviderTestCase


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_T = t.TypeVar('_T')


class ValueProviderTests(ProviderTestCase):
    

    @pytest.fixture
    def provider(self, value_factory):
        self.value = value_factory()
        return Provider(_T, self.value)



