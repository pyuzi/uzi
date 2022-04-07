import typing as t 
from collections.abc import Callable
from functools import partial, update_wrapper


from xdi import Scope, providers
from sanic import Request, Sanic



def inject(handler: Callable):
    if isinstance(handler, partial):
        func = handler.func
    else:
        func = handler      

    if hasattr(func, '__dependency__'):
        return handler

    provider = providers.Partial(func)

    def wrapper(req: Request, *a, **kw):
        nonlocal provider
        return req.ctx.injector_context[provider](req, *a, **kw)
    
    update_wrapper(wrapper, func)
    wrapper.__dependency__ = provider

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