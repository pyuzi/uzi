from collections import ChainMap
from collections.abc import Mapping

import typing as t
from django.http.request import QueryDict
from djx.abc.api import FormList, QueryList
from djx.common.collections import Arguments, MappingProxy, factorydict, frozendict 



from djx.di  import get_ioc_container, IocContainer

from djx.di.common import InjectorVar
from djx.di.injectors import Injector
from djx.di.providers import Provider
from djx.di.scopes import Scope

from djx.abc import Settings
from djx.api.abc import (
    Args, Inputs, Kwargs, Request, Query, RawBody,
    Body, Form, Params, Files, 
    Cookies, Headers, BodyParser, 
    Session, Arguments
)

from djx.api import Request as DjangoRequest
from djx.core.util import django_settings


if t.TYPE_CHECKING:
    Request = DjangoRequest



ioc = get_ioc_container()


ioc.function(Settings, django_settings, at='main', cache=True, priority=-1)



# def _provide_request_attr(name):
    
#     def provide(self: Provider, scope: Scope, token):
#         def resolve(inj: Injector):
#             if var := inj.vars[DjangoRequest]:
#                 # req = var.get()
#                 # def make():
#                 #     nonlocal name, var, req
#                 #     return getattr(req, name)
                    
#                 return InjectorVar(inj, value=getattr(var.value, name)) 

#         return resolve, {DjangoRequest}
#     return provide


_injkwds = dict(
    at='request',
    cache=True,
    priority=-1
)


@ioc.provide(Form, **_injkwds)
def _provider(self: Provider, scope: Scope, token):
    def resolve(inj: Injector):
        if var := inj.vars[DjangoRequest]:
            return InjectorVar(inj, value=var.value.POST) 
    return resolve, {DjangoRequest}


@ioc.provide(FormList, **_injkwds)
def _provider(self: Provider, scope: Scope, token):
    def resolve(inj: Injector):
        return InjectorVar(inj, value=factorydict(inj[Form].getlist)) 
    
    return resolve, {Form}



@ioc.provide(Files, **_injkwds)
def _provider(self: Provider, scope: Scope, token):
    def resolve(inj: Injector):
        if var := inj.vars[DjangoRequest]:
            return InjectorVar(inj, value=var.value.FILES) 
    return resolve, {DjangoRequest}



@ioc.provide(Query, **_injkwds)
def _provider(self: Provider, scope: Scope, token):
    def resolve(inj: Injector):
        if var := inj.vars[DjangoRequest]:
            return InjectorVar(inj, value=var.value.GET) 
    return resolve, {DjangoRequest}


@ioc.provide(QueryList, **_injkwds)
def _provider(self: Provider, scope: Scope, token):
    def resolve(inj: Injector):
        return InjectorVar(inj, value=factorydict(inj[Query].getlist)) 
    
    return resolve, {Query}



@ioc.provide(Cookies, **_injkwds)
def _provider(self: Provider, scope: Scope, token):
    def resolve(inj: Injector):
        if var := inj.vars[DjangoRequest]:
            return InjectorVar(inj, value=var.value.COOKIES) 
    return resolve, {DjangoRequest}




@ioc.provide(RawBody, **_injkwds)
def _provider(self: Provider, scope: Scope, token):
    def resolve(inj: Injector):
        if var := inj.vars[DjangoRequest]:
            return InjectorVar(inj, value=var.value.body) 
    return resolve, {DjangoRequest}


@ioc.provide(Session, **_injkwds)
def _provider(self: Provider, scope: Scope, token):
    def resolve(inj: Injector):
        if var := inj.vars[DjangoRequest]:
            return InjectorVar(inj, value=var.value.session) 
    return resolve, {DjangoRequest}




# ioc.provide(Files, _provide_request_attr('FILES'), **_injkwds)

# ioc.provide(Query, _provide_request_attr('GET'), **_injkwds)

# ioc.provide(Cookies, _provide_request_attr('COOKIES'), **_injkwds)


# ioc.provide(Headers, _provide_request_attr('META'), **_injkwds)

# ioc.provide(RawBody, _provide_request_attr('body'), **_injkwds)
# ioc.provide(Session, _provide_request_attr('session'), **_injkwds)


@ioc.function(Headers, **_injkwds)
def _make_headers(req: DjangoRequest):
    return MappingProxy(req.META, fallback=req.headers)

    

@ioc.provide(Body, **_injkwds)
def _provider(self: Provider, scope: Scope, token):
    def resolve(inj: Injector):
        if var := inj.vars[DjangoRequest]:
            req: DjangoRequest = var.value
            if req.POST:
                return InjectorVar(inj, value=ChainMap(req.POST, req.FILES)) 
            elif raw := req.body:
                return InjectorVar(inj, value=inj[BodyParser].parse(raw, None)) 
            return InjectorVar(inj, value=None) 

    return resolve, {DjangoRequest, RawBody, BodyParser}


# def _parse_body(raw: RawBody, parser: BodyParser, req: DjangoRequest=None):
#     if req and req.POST:
#         return ChainMap(req.POST, req.FILES)
    
#     return (raw or None) and parser.parse(raw, None)
    


@ioc.provide(Args, **_injkwds)
def _make_arguments(self: Provider, scope: Scope, token):
    def resolve(inj: Injector):
        if var := inj.vars[DjangoRequest]:
            req: DjangoRequest = var.value

            return InjectorVar(inj, value=req.resolver_match.args) 
    return resolve, {DjangoRequest}

    # if match := req.resolver_match:
    #     return match.args
    # # raise AttributeError(f"request {req.__class__.__name__!r} has not attribute 'resolver_match'")
    



# @ioc.function(Kwargs, **_injkwds)
# def _make_arguments(req: DjangoRequest):
#     if match := req.resolver_match:
#         return match.kwargs
#     # raise AttributeError(f"request {req.__class__.__name__!r} has not attribute 'resolver_match'")
    

@ioc.provide(Kwargs, **_injkwds)
def _make_arguments(self: Provider, scope: Scope, token):
    def resolve(inj: Injector):
        if var := inj.vars[DjangoRequest]:
            req: DjangoRequest = var.value

            return InjectorVar(inj, value=req.resolver_match.kwargs) 
    return resolve, {DjangoRequest}




@ioc.function(Arguments, **_injkwds)
def _make_arguments(args: Args=None, kwargs: Kwargs=None):
    return Arguments(args, kwargs)





@ioc.function(Params, **_injkwds)
def _makeparams(path: Kwargs=None, 
                query: Query=None, 
                body: Body=None, 
                headers: Headers=None, /):
    ok = False
    res = ChainMap(*(
            m for m in (
                path,
                query,
                body if isinstance(body, Mapping) else None,
                headers,
            ) if m is not None
        ))

    if ok is False:
        raise ValueError(f"request params not available.")

    return res






@ioc.function(Inputs, **_injkwds)
def _make_input(query: Query=None, 
                body: Body=None, /):

    res = ChainMap(*([
            m for m in (
                body if isinstance(body, Mapping) else None,
                query,
            ) if m
        ] or [frozendict(),]
    ))

    return res



