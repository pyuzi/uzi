import asyncio
import typing as t
import attr

import pytest
from xdi import Dep, InjectionMarker
from xdi.providers import AnnotatedProvider as Provider

from .abc import ProviderTestCase, AsyncProviderTestCase
from .union_tests import UnionProviderTests


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_Ta = t.TypeVar("_Ta")
_Tb = t.TypeVar("_Tb")


_Ann = object()


@attr.s(frozen=True)
class Marker(InjectionMarker):
    name = attr.ib(default='<MARKER>')

    @property
    def __dependency__(self):
        return self.__class__



class AnnotatedProviderTests(UnionProviderTests[Provider]):

    expected = {
        t.Annotated[_Ta, _Ann, Dep(_Tb), t.Literal['abc'], None]: [
            (Dep(_Tb), _Ta), 
            (Dep(_Tb), _Ta)
        ],   
        t.Annotated[t.Literal['abc'], Dep(_Ta), Provider, Marker()]: [
            (Marker(), Dep(_Ta), t.Literal['abc']),
            (Marker(), Dep(_Ta)),
        ], 
        t.Annotated[Provider, Dep(_Ta), Provider, Marker()]: [
            (Marker(), Dep(_Ta), Provider),
            (Marker(), Dep(_Ta), Provider),
        ],
    }
    
    @pytest.fixture(params=expected.keys())
    def abstract(self, request):
        return request.param




# class AsyncAnnotatedProviderTests(AnnotatedProviderTests, AsyncProviderTestCase):

    
#     @pytest.fixture
#     def scope(self, scope, value_setter):
#         fn = lambda inj: value_setter
#         fn.is_async = True
#         scope[_Ta] = fn
#         return scope

