import typing as t 
from django.urls import path, include
from djx.api.params import Body, Query, Param, Input
from djx.common.utils import assign
from djx.di import get_ioc_container
from ninja import NinjaAPI
import ninja as nja
from django.http import JsonResponse, HttpRequest
from djx.common import json, moment

from djx.schemas import OrmSchema, EmailStr, Schema, constr


from .func_views import ViewFunction
from .views import GenericView, action


from djx.iam import UserModel, UserRole, UserStatus

from . import Request, HttpResponse, mixins
from .types import HttpMethod

from .routers import DefaultRouter

router = DefaultRouter()




class UserIn(Schema):
    name: str
    role: UserRole = UserRole.SUBSCRIBER
    email: EmailStr
    password: constr(min_length=5)

    # phone: str



class UserOut(OrmSchema):
    pk: int
    name: str
    status: UserStatus
    role: UserRole
    email: EmailStr
    username: str
    created_at: moment.Moment



class UsersView(mixins.CrudModelMixin):

    # __slots__ = ()

    class Config:
        queryset = UserModel.objects.order_by('created_at')
        request_schema = UserIn
        response_schema = UserOut




router.register('users', UsersView)



ioc = get_ioc_container()

njapi = NinjaAPI()




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
    # path("jani/test/<p1>/<p2>", func.view), 
    # path('users/', UsersView.as_view({'get': 'list', 'put': 'create'})),
    # path('ninja/', njapi.urls),
    path('', include(router.urls)),
]