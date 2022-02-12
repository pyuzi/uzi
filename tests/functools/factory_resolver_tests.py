from email.policy import default
import pytest
from inspect import Parameter




from laza.di.functools import FactoryResolver, _EMPTY
from laza.di.common import Dep


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize





class FactoryResolverTests:

    def test_basic(self):
        res = FactoryResolver(lambda:...)
        
        