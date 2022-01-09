import typing as t 
from django.urls import path, include
from jani.api.params import Body, Query, Param, Input
from jani.api.params.fields import Path
from jani.di import get_ioc_container
from ninja import NinjaAPI
import ninja as nja
from django.http import JsonResponse, HttpRequest
from jani.common import json


from .func_views import ViewFunction


ioc = get_ioc_container()

njapi = NinjaAPI()


@ioc.injectable(cache=True)
class Foo:
    __slots__ = 'foo'

    foo: t.Any




_T = t.TypeVar('_T')
_T_Foo = t.TypeVar('_T_Foo', bound=Foo)



# @ViewFunction
# def func(
#         p1: t.Literal['xyz', 'abc']=Path(),
#         p2: int=Path(),
#         a: str = Query(), 
#         b: str = Query(), 
#         age: int = Body(),
#         foo: bool = Body(), 
#         bar: str = Body(), 
#         baz: str = Body(), 
#         ):
#     return JsonResponse(dict(a=a, b=b, p1=p1, p2=p2, age=age, foo=foo, bar=bar, baz=baz))



@ViewFunction
def func(
        p1: t.Annotated[t.Literal['xyz', 'abc'], Path()],
        p2: t.Annotated[int, Path()],
        a: str, # t.Annotated[str, Query()], 
        b: str, # t.Annotated[str, Query()],
        age: t.Annotated[int, Body()],
        foo: Foo, 
        bar: t.Annotated[str, Body()], 
        baz: t.Annotated[str, Body()]):
    return JsonResponse(dict(a=a, b=b, p1=p1, p2=p2, age=age, foo=f'{foo.__class__.__module__}.{foo.__class__.__name__}', bar=bar, baz=baz))


def valid_view(req, *a, **kw):
    if req.method == 'POST':
        data = json.loads(req.body)
    else:
        data = dict()

    data.update(kw, a=req.GET['a'], b=req.GET['b'])
    
    return func.run(**data)



def plain_view(req, *a, **kw):
    if req.method == 'POST':
        data = json.loads(req.body)
    else:
        data = dict()
    
    data.update(kw, a=req.GET['a'], b=req.GET['b'])
    return func.func(**data)

    # return func.func(
    #     typs['a'](req.GET['a']), 
    #     typs['b'](req.GET['b']), 
    #     **{ k : typs[k](v) for k,v in data.items() 
    # })


@njapi.post('/test/{p1}/{p2}')
def ninja_view(request: HttpRequest, 
        p1: t.Literal['xyz', 'abc'],
        p2: int,
        # xx: t.Iterable[str] = None,
        # yy: t.Iterable[int] = None,
        a: str = nja.Query(...), 
        b: str = nja.Query(...), 
        age: int = nja.Body(...),
        foo: bool = nja.Body(...), 
        bar: str = nja.Body(...),
        baz: str = nja.Body(...)
        ) -> JsonResponse:
    
    return JsonResponse(dict(a=a, b=b, p1=p1, p2=p2, age=age, foo=foo, bar=bar, baz=baz))




urlpatterns = [
    path("jani/test/<p1>/<p2>", func.view), 
    path('ninja/', njapi.urls),

    path("valid/test/<p1>/<p2>", valid_view), 
    path("plain/test/<p1>/<p2>", plain_view), 
]