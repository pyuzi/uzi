from django.http import HttpResponse, HttpRequest, JsonResponse
from django.views import View


from rest_framework import mixins
from rest_framework.generics import GenericAPIView
from rest_framework.views import APIView


from jani.multisite.models import impl 
from jani.core import views

from time import time

_last_tick = 0
_ticks = []

def tick(req):
    global _last_tick, _ticks
    if time() - _last_tick >= 2.5:
        _last_tick = time()
        _ticks.append(_last_tick)
        print(f' - {str(len(_ticks)).rjust(2, "0")} tick: {req.path}')




def func(req: HttpRequest):
    tick(req)
    return HttpResponse(f'{req.path}')    



class Dj(View):

    def get(self, req: HttpRequest):
        tick(req)
        return HttpResponse(f'{req.path}')    

    


class Jani(views.View):

    def get(self, req: HttpRequest):
        tick(req)
        return HttpResponse(f'{req.path}')    

    


class Rest(GenericAPIView):

    def get(self, req: HttpRequest):
        return HttpResponse(f'{req.path}')    

    