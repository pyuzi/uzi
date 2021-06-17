
from .const import *

from django.http.request import HttpRequest
from django.http.response import HttpResponseBase as HttpResponse


from djx.di import di
from .. import abc

di.alias(HttpRequest, abc.Request, scope=di.REQUEST_SCOPE)