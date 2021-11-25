import typing as t 
from django.urls import path, include
from djx.di import get_ioc_container
from ninja import NinjaAPI





ninja = NinjaAPI()

from .views import djx, drf






urlpatterns = [
    # path("jani/test/<p1>/<p2>", func.view), 
    # path('users/', UsersView.as_view({'get': 'list', 'put': 'create'})),
    # path('ninja/', njapi.urls),

    path('djx/', include(djx.router.urls)),
    path('drf/', include(drf.router.urls)),
    # path('api/drf/', include(router.urls)),
]