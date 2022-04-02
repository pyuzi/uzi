import pytest

import typing as t



from xdi.providers import Resource as Provider


from .contextmanager_tests import ContextManagerProviderTests

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize



        


class ResourceProviderTests(ContextManagerProviderTests):
    
    @pytest.fixture
    def provider(self, cm):
        return Provider(lambda: cm)


