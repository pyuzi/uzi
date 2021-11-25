import typing as t 
import pytest
from django.test import Client as DjClient, RequestFactory


from time import monotonic, sleep, time


from djx.di import get_ioc_container
from djx.abc.api import  Request
from djx.core.test import Client
from djx.api.params import Body, Query, Param, Input



__djx_schema_namespace__ = 'test'


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


ioc = get_ioc_container()




class DecoratorTests:

    def _test_with_request(self, speed_profiler):
        rfactory = RequestFactory()

        url = '/api/{}/test/xyz/1234?a=aa&b=bb'

        rargs = dict(foo=False, age='22', bar='In the bar', baz='Why cause a fuz when you can buz'),
        rkwds = dict(content_type='application/json')

        def make_req(path):
            rfactory.post(url.format(path), *rargs, **rkwds)


        rjani = make_req('jani')

    @pytest.mark.urls('djx.api.urls__funcbased')
    def _test_with_client(self, speed_profiler):

        client = Client()
        dj_client = DjClient()
        dj_client = client
        

        rargs = dict(age='22', bar='In the bar', baz='Why cause a fuz when you can buz'),
        rkwds = dict(content_type='application/json')

        url = '/{}/test/xyz/1234?a=aa&b=bb'

        fjani = lambda: client.post(url.format('jani'), *rargs, **rkwds)
        # fnja = lambda: client.post('/api/djx?a=aa&b=bb', dict(foo=False, age='22', bar='In the bar'))
        fninja = lambda: dj_client.post(url.format('ninja'), dict(rargs[0], foo=False), *rargs[1:], **rkwds)
        fplain = lambda: dj_client.post(url.format('plain'), dict(rargs[0], foo=False), *rargs[1:], **rkwds)
        # fvalid = lambda: dj_client.post(url.format('valid'), *rargs, **rkwds)
        
        vardump(
            __plain__=fplain().content, 
            # __valid__=fvalid().content, 
            __janix__=fjani().content,
            __ninja__=fninja().content
        )
        


        # assert 0
        _n = 200
        r = 3 
        col = 60

        st = monotonic()

        print(' '*col)
        print('-'*col)
        for i in range(0,3,4):
            
            targs = [
                ('ninja', fninja), 
                ('janix', fjani), 
            ]

            for lbl, fn in targs:
                profile = speed_profiler(_n, labels=(lbl, 'plain'), repeat=r)
                profile(fn, fplain, f'{lbl.upper()} ')
                sleep(.1)
                # profile = speed_profiler(_n, labels=(lbl, 'valid'), repeat=r)
                # profile(fn, fvalid, f'{lbl.upper()} ')
                # print('-'*col)
                # sleep(.1)
            print(' '*col)

        _n = int(8e2)
        r = 3

        for _ in range(2):
            profile = speed_profiler(_n, labels=('ninja', 'janix'), repeat=r)
            profile(fninja, fjani, f'ninja-vs-janix')
            sleep(.1)

            profile = speed_profiler(_n, labels=('janix', 'ninja'), repeat=r)
            profile(fjani, fninja, f'janix-vs-ninja')

            print('-'*col)
            sleep(.1)

        tt = monotonic() - st
        print(f'TOOK: {round(tt, 4)} secs')
        print('='*col)

        assert False
        # 