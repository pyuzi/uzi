import typing as t
from djx.common.utils.data import DataPath 
import pytest
from django.test import Client as DjClient, RequestFactory




from djx.di import get_ioc_container
from djx.abc.api import  Request
from djx.core.test import Client
from djx.api.views import View, GenericView, action
from djx.schemas import Schema


__djx_schema_namespace__ = 'test'


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


ioc = get_ioc_container()

@pytest.mark.django_db()
class ViewActionTests:

    @xfail(raises=RuntimeError)
    def test_action_on_noneview(self):
        class NotView:
    
            @action
            def abc(self):
                ...

    # @pytest.mark.urls('djx.api.tests.urls')
    def test_compare(self, speed_profiler):
        
        client = Client()
        dj_client = DjClient()
        dj_client = client
        

        rargs = () #dict(age='22', bar='In the bar', baz='Why cause a fuz when you can buz'),
        rkwds = dict(content_type='application/json')

        url = 'api/{}/users/'

        fdjx = lambda: client.post(url.format('djx'), *rargs, **rkwds)
        fdrf = lambda: client.post(url.format('drf'), *rargs, **rkwds)
    
        vardump(
            __djx__=fdjx().content,
            __drf__=fdrf().content
        )
        
        _n = 5e2
        r = 2

        profile = speed_profiler(_n, labels=('djx', 'drf'), repeat=r)
        profile(fdjx, fdrf, f'djx-vs-drf')


        assert 0