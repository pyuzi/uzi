from types import FunctionType, MethodType
import typing as t 
from collections.abc import Callable
from functools import partial, update_wrapper

from xdi import Scope, providers

try:
    from sanic import Request, Sanic
    from sanic.router import Router
except ImportError as e: #progma: no cover
    raise ImportError(f'`{__package__!r}` requires `sanic` installed.')







def inject(handler: Callable, /, *args, **kwds):
    if isinstance(handler, partial):
        func = handler.func
    else:
        func = handler      

    if hasattr(func, '__xdi_provider__'):
        raise ValueError(f'{handler!s} already wired')
    elif isinstance(func, MethodType):
        func, *args = func.__func__, func.__self__, *args

    provider = providers.Partial(func, *args, **kwds)

    def wrapper(req: t.Union[Sanic, Request, Router], *a, **kw):
        nonlocal provider
        return req.ctx._xdi_injector(provider, req, *a, **kw)
    
    update_wrapper(wrapper, func)
    wrapper.__xdi_provider__ = provider

    return wrapper





def extend_app(app: Sanic, injector: Scope, *, inject_routes: bool=True, inject_middleware=True):

    @app.on_request
    def setup_request_injector(request: Request):
        request.ctx.injector_context = injector.create_context()

    @app.on_response
    async def teardown_request_injector(request: Request, res):
        await request.ctx.injector_context.exitstack.aclose()

    # if inject_routes:
    #     @app.after_server_start
    #     def wrap_injectables(app: Sanic):
    #         if inject_routes:
    #             for route in app.router.routes:
    #                 if ".openapi." in route.name:
    #                     continue
    #                 handlers = [(route.name, route.handler)]
    #                 viewclass = getattr(route.handler, "view_class", None)
    #                 if viewclass:
    #                     pass
                        
    #                 for name, handler in handlers:
    #                     if hasattr(handler, "__auto_handler__"):
    #                         continue
    #                     if isinstance(handler, partial):
    #                         if handler.func == app._websocket_handler:
    #                             handler = handler.args[0]
    #                         else:
    #                             handler = handler.func
                        
    #                     injections: Dict[
    #                         str, Tuple[Type, Optional[Callable[..., Any]]]
    #                     ] = {
    #                         param: (
    #                             annotation,
    #                             injection_registry[annotation],
    #                         )
    #                         for param, annotation in hints.items()
    #                         if annotation in injection_registry
    #                     }
    #                     registry.register(name, injections)



    return app