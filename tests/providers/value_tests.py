import pytest

import typing as t



from xdi.providers import Value as Provider


from .abc import ProviderTestCase


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_T = t.TypeVar('_T')


class ValueProviderTests(ProviderTestCase[Provider]):

    @pytest.fixture
    def concrete(self, value_setter):
        return value_setter()



