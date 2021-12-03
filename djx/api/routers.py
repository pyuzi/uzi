import typing as t 
from itertools import chain, groupby
from collections import ChainMap, OrderedDict, namedtuple

from django.urls import NoReverseMatch, re_path

from djx.common.collections import fallbackdict, frozendict, nonedict, orderedset
from djx.common.exc import ImproperlyConfigured

from .urlpatterns import format_suffix_patterns
from .abc import Response
from .views import View, GenericView, ActionRouteDescriptor
from .types import T_HttpMethodStr, Route, DynamicRoute, HttpMethod

api_settings = None


    

def _escape_curly_brackets(url_path):
    """
    Double brackets in regex of url_path for escape string formatting
    """
    return url_path.replace('{', '{{').replace('}', '}}')



class BaseRouter:
    def __init__(self):
        self.registry = []

    def register(self, prefix, view, basename=None):
        if basename is None:
            basename = self.get_default_basename(view)
        self.registry.append((prefix, view, basename))

        # invalidate the urls cache
        if hasattr(self, '_urls'):
            del self._urls

    def get_default_basename(self, view):
        """
        If `basename` is not specified, attempt to automatically determine
        it from the viewset.
        """
        raise NotImplementedError('get_default_basename must be overridden')

    def get_urls(self):
        """
        Return a list of URL patterns, given the registered viewsets.
        """
        raise NotImplementedError('get_urls must be overridden')

    @property
    def urls(self):
        if not hasattr(self, '_urls'):
            self._urls = self.get_urls()
        return self._urls


class SimpleRouter(BaseRouter):

    routes: list[t.Union[Route, DynamicRoute]] = [
        # List route.
        Route(
            url=r'^{prefix}{trailing_slash}$',
            name='{basename}-list',
            # mapping={ m.name: m.name.lower() for m in HttpMethod },
            mapping={
                'GET': 'get',
                'POST': 'post',
            },
            detail=False,
            initkwargs={'suffix': 'List'}
        ),
        DynamicRoute(
            url=r'^{prefix}/{url_path}{trailing_slash}$',
            name='{basename}-{url_name}',
            detail=False,
            initkwargs={}
        ),
        Route(
            url=r'^{prefix}/{lookup}{trailing_slash}$',
            name='{basename}-detail',
            mapping={
                'GET': 'get',
                'PUT': 'put',
                'PATCH': 'patch',
                'DELETE': 'delete'
            },
            # name='{basename}-detail',
            # mapping = { m.name: m.name.lower() for m in ~HttpMethod.POST },
            detail=True,
            initkwargs={'suffix': 'Instance'},
        ),
        DynamicRoute(
            url=r'^{prefix}/{lookup}/{url_path}{trailing_slash}$',
            name='{basename}-{url_name}',
            detail=True,
            initkwargs={}
        ),
    ]

    def __init__(self,  *, trailing_slash=True):
        self.trailing_slash = '/' if trailing_slash else ''
        super().__init__()

    def get_default_basename(self, view: type[View]):
        """
        If `basename` is not specified, attempt to automatically determine
        it from the viewset.
        """
        return view.__config__.basename

    def get_routes(self, view: type[View]):
        """
        Augment `self.routes` with any dynamically generated routes.

        Returns a list of the Route namedtuple.
        """
        # converting to list as iterables are good for one pass, known host needs to be checked again and again for
        # different functions.

        actions = view.get_all_action_descriptors()

        items = sorted(((n, m) for route in self.routes if isinstance(route, Route) for m, n in route.mapping.items()))

        known_actions = {
            n: {x[1] for x in g}
            for n, g in groupby(items, lambda i: i[0])
        }

        implied = { m.name.lower(): {m.name} for m in HttpMethod }
        
        details = { n: r for n, a in actions.items() if (r := a.detail_route())}
        outlines = { n: r for n, a in actions.items() if (r := a.outline_route())}
        ambiguous = { n: r for n, a in actions.items() if (r := a.implicit_route())}

        all_actions = ChainMap(ambiguous, details, outlines)

        root_outline_actions = { 
            k : r 
            for k, a in actions.items()
                if k in known_actions and not (a.url_path or a.url_name) 
                    and not a.mapping.keys() - known_actions[k]
                    and (r := outlines.pop(k, None) or ambiguous.get(k, None))
        }

        root_detail_actions = { 
            k : r 
            for k, a in actions.items()
                if k in known_actions and not (a.url_path or a.url_name) 
                    and not a.mapping.keys() - known_actions[k]
                    and (r := details.pop(k, None) or ambiguous.get(k, None))
        }

    
        for k, ms in implied.items():
            a = actions.get(k)
            if a and not (a.url_path or a.url_name or a.mapping.keys() - ms):
                for d in all_actions.maps:
                    d.pop(k, None)


        if not_allowed := orderedset(ambiguous) - known_actions:
            not_allowed = list(not_allowed)
            if len(not_allowed) > 1:
                actstr = f'actions `{"`, `".join(not_allowed[:-1])}` and `{not_allowed[-1]}`'
            else:
                actstr = f'action `{not_allowed[0]}`'
            raise ImproperlyConfigured(
                    f'Provide argument(s) `detail` or/and `outline` to aviod '
                    f'ambiguity on {actstr} in {view.__name__!r}.'
                )
        elif not_allowed := orderedset(all_actions) & (known_actions | implied):
            not_allowed = list(not_allowed)
            if len(not_allowed) > 1:
                actstr = f'actions `{"`, `".join(not_allowed[:-1])}` and `{not_allowed[-1]}`'
            else:
                actstr = f'action `{not_allowed[0]}`'
            raise ImproperlyConfigured(
                    f'Reserved {actstr.title()} in {view.__name__!r} '
                    f'cannot contain custom `url_path`, `url_name` or `mapping`.'
                )
    
        # # partition detail and list actions
        # detail_actions = [action for action in extra_actions if action.detail]
        # list_actions = [action for action in extra_actions if not action.detail]


        rmap = {
            (Route, False): root_outline_actions,
            (Route, True): root_detail_actions,
            (DynamicRoute, False): outlines,
            (DynamicRoute, True): details,
        }

        routes = [
            r for c in self.routes 
                for r in self._iter_make_routes(c, rmap[c.key], actions)
        ]

        return routes

    def _iter_make_routes(self, 
                        conf: t.Union[Route, DynamicRoute], 
                        routes: dict[str, Route],
                        actions: dict[str, ActionRouteDescriptor], ):

        if isinstance(conf, DynamicRoute):
            for k, r in routes.items():
                yield self._make_dynamic_route(conf, actions[k], r.url, r.name, r.mapping)
        elif conf.mapping:
            yield conf._replace(
                mapping = {
                    m: k for m, k in conf.mapping.items()
                    if k in routes and routes[k].mapping.get(m)
                }
            )
            

    def _make_dynamic_route(self, 
                        conf: t.Union[Route, DynamicRoute], 
                        action: ActionRouteDescriptor, 
                        url_path: t.Optional[str], 
                        url_name: t.Optional[str],
                        mapping: dict[T_HttpMethodStr, str], *, is_root=False):

        
        url_path = _escape_curly_brackets(url_path or action.slug).strip()
        url_name = f'{url_name or action.slug}'.strip()

        # vardump(action, conf.detail, action.mapping)

        if action.is_outline() and action.is_detail():
            if conf.detail:
                url_name = f'detail-{url_name}'.strip('-')
            # else:
            #     url_name = f'list-{url_name}'.strip('-')

        res = Route(
            url=conf.url.replace('{url_path}', url_path),
            name=conf.name.replace('{url_name}', url_name),
            mapping=mapping,
            detail=conf.detail,
            initkwargs=conf.initkwargs,
        )

        return res

    def _get_root_route(self, route: Route, present: dict[str, Route]):
        return route._replace(

        )
    
    def get_method_map(self, view: type[View], method_map):
        """
        Given a viewset, and a mapping of http methods to actions,
        return a new mapping which only includes any mappings that
        are actually implemented by the viewset.
        """
        bound_methods = {}

        view.__config__.get_method_map()

        # vardump(view.__name__, method_map)

        for method, action in method_map.items():
            if view.__config__.has_action(action):
                bound_methods[method] = action
        
        return bound_methods

    def get_lookup_regex(self, view: type[GenericView], lookup_prefix=''):
        """
        Given a viewset, return the portion of URL regex that is used
        to match against a single instance.

        Note that lookup_prefix is not used directly inside REST rest_framework
        itself, but is required in order to nicely support nested router
        implementations, such as drf-nested-routers.

        https://github.com/alanjds/drf-nested-routers
        """
        base_regex = '(?P<{lookup_prefix}{lookup_url_kwarg}>{lookup_value})'
        # Use `pk` as default field, unset set.  Default regex should not
        # consume `.json` style suffixes and should break at '/' boundaries.
        config = view.__config__

        lookup_field = config.get('lookup_field') or 'pk' 
        lookup_url_kwarg = config.get('lookup_url_kwarg') or lookup_field
        lookup_value = config.get('lookup_value_regex') or '[^/.]+'

        return base_regex.format(
            lookup_prefix=lookup_prefix,
            lookup_url_kwarg=lookup_url_kwarg,
            lookup_value=lookup_value
        )

    def get_urls(self):
        """
        Use the registered viewsets to generate a list of URL patterns.
        """
        ret = []

        for prefix, view, basename in self.registry:
            lookup = self.get_lookup_regex(view)
            routes = self.get_routes(view)

            for route in routes:

                # Only actions which actually exist on the viewset will be bound
                mapping = self.get_method_map(view, route.mapping)
                if not mapping:
                    continue

                # Build the url pattern
                regex = route.url.format(
                    prefix=prefix,
                    lookup=lookup,
                    trailing_slash=self.trailing_slash
                )

                # If there is no prefix, the first part of the url is probably
                #   controlled by project's urls.py and the router is in an app,
                #   so a slash in the beginning will (A) cause Django to give
                #   warnings and (B) generate URLS that will require using '//'.
                if not prefix and regex[:2] == '^/':
                    regex = '^' + regex[2:]

                initkwargs = route.initkwargs.copy()
                initkwargs.update({
                    'basename': basename,
                    'detail': route.detail,
                })

                func = view.as_view(mapping, **initkwargs)
                name = route.name.format(basename=basename)
                ret.append(re_path(regex, func, name=name))

        return ret


class DefaultRouter(SimpleRouter):
    """
    The default router extends the SimpleRouter, but also adds in a default
    API root view, and adds format suffix patterns to the URLs.
    """
    include_root_view = False
    include_format_suffixes = False
    root_view_name = 'api-root'
    default_schema_renderers = None
    
    def get_urls(self):
        """
        Generate the list of URL patterns, including a default root view
        for the API, and appending `.json` style format suffixes.
        """
        urls = super().get_urls()

        vardump(urls)

        if self.include_format_suffixes:
            urls = format_suffix_patterns(urls)

        return urls
