from logging import getLogger
import typing as t 

from django.test.client import Client, ClientHandler as BaseClientHandler


from djx.di import get_ioc_container, REQUEST_SCOPE

from ..handlers.core import InjectorContextHandler


from djx.abc.api import Request



logger = getLogger(__name__)


class ClientHandler(BaseClientHandler):
    
    ioc = get_ioc_container()
    di_scope = REQUEST_SCOPE
    
    def get_response(self, request):
        ioc = self.ioc
        # inj, token = ioc.use(self.di_scope)
        # inj[Request] = request

        # # logger.debug('___START___')
        # res = BaseClientHandler.get_response(self, request)
        # # logger.debug('___ENDD___')
        # token is None or ioc.ctxvar.reset(token)  

        # return res
        with self.ioc.use(self.di_scope) as inj:
            inj[Request] = request
            return super().get_response(request)

    # def get_response(self, request: HttpRequest) -> HttpResponse:
    #     self._provide_request(request)
    #     return super().get_response(request)
    



class Client(Client):
    

    def __init__(self, enforce_csrf_checks=False, raise_request_exception=True, **defaults):
        super().__init__(enforce_csrf_checks, raise_request_exception, **defaults)
        self.handler = ClientHandler(enforce_csrf_checks)
