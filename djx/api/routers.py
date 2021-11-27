import typing as t 
import itertools
from collections import OrderedDict, namedtuple

from django.urls import NoReverseMatch, re_path
from djx.api.views.core import ActionMethod

from djx.common.collections import frozendict
from djx.common.exc import ImproperlyConfigured

from .urlpatterns import format_suffix_patterns
from .abc import Response
from .views import View
from .types import HttpMethod, MethodMapper, ActionMethod, T_HttpMethodStr

api_settings = None


class Route(t.NamedTuple):
    url: str
    mapping: dict[T_HttpMethodStr, str]
    name: str
    detail: bool
    initkwargs: dict[str, t.Any] = frozendict()

    
class DynamicRoute(t.NamedTuple):
    url: str
    name: str
    detail: bool
    initkwargs: dict[str, t.Any] = frozendict()

    

def _escape_curly_brackets(url_path):
    """
    Double brackets in regex of url_path for escape string formatting
    """
    return url_path.replace('{', '{{').replace('}', '}}')


def _flatten(list_of_lists):
    """
    Takes an iterable of iterables, returns a single iterable containing all items
    """
    return itertools.chain(*list_of_lists)


class BaseRouter:
    def __init__(self):
        self.registry = []

    def register(self, prefix, viewset, basename=None):
        if basename is None:
            basename = self.get_default_basename(viewset)
        self.registry.append((prefix, viewset, basename))

        # invalidate the urls cache
        if hasattr(self, '_urls'):
            del self._urls

    def get_default_basename(self, viewset):
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

    routes = [
        # List route.
        Route(
            url=r'^{prefix}{trailing_slash}$',
            mapping={
                'GET': 'list',
                'POST': 'post'
            },
            name='{basename}-list',
            detail=False,
            initkwargs={'suffix': 'List'}
        ),
        # List route.
        # Route(
        #     url=r'^{prefix}{trailing_slash}$',
        #     mapping={
        #         'get': 'list',
        #         # 'post': 'post'
        #     },
        #     name='{basename}-list',
        #     detail=False,
        #     initkwargs={'suffix': 'List'}
        # ),
        # Dynamically generated list routes. Generated using
        # @action(detail=False) decorator on methods of the viewset.
        DynamicRoute(
            url=r'^{prefix}/{url_path}{trailing_slash}$',
            name='{basename}-{url_name}',
            detail=False,
            initkwargs={}
        ),
        # Detail route.
        # Route(
        #     url=r'^{prefix}/{lookup}{trailing_slash}$',
        #     mapping={
        #         'get': ('get', 'retrieve'),
        #         'put': ('put', 'update'),
        #         'patch': ('patch', 'partial_update'),
        #         'delete': ('delete', 'destroy')
        #     },
        #     name='{basename}-detail',
        #     detail=True,
        #     initkwargs={'suffix': 'Instance'}
        # ),
        # Detail route.
        Route(
            url=r'^{prefix}/{lookup}{trailing_slash}$',
            mapping={
                'GET': 'get',
                'PUT': 'put',
                'PATCH': 'patch',
                'DELETE': 'delete'
            },
            name='{basename}-detail',
            detail=True,
            initkwargs={'suffix': 'Instance'}
        ),
        # Dynamically generated detail routes. Generated using
        # @action(detail=True) decorator on methods of the viewset.
        DynamicRoute(
            url=r'^{prefix}/{lookup}/{url_path}{trailing_slash}$',
            name='{basename}-{url_name}',
            detail=True,
            initkwargs={}
        ),
    ]

    def __init__(self, *, trailing_slash=True):
        self.trailing_slash = '/' if trailing_slash else ''
        super().__init__()

    def get_default_basename(self, viewset):
        """
        If `basename` is not specified, attempt to automatically determine
        it from the viewset.
        """
        
        queryset = getattr(viewset.__config__, 'queryset', None)
        
        assert queryset is not None, '`basename` argument not specified, and could ' \
            'not automatically determine the name from the viewset, as ' \
            'it does not have a `.queryset` attribute.'

        return queryset.model._meta.object_name.lower()

    def get_routes(self, view: type[View]):
        """
        Augment `self.routes` with any dynamically generated routes.

        Returns a list of the Route namedtuple.
        """
        # converting to list as iterables are good for one pass, known host needs to be checked again and again for
        # different functions.
        known_actions = set(_flatten([route.mapping.values() for route in self.routes if isinstance(route, Route)]))
        extra_actions = view.get_extra_actions(known=known_actions)

        # checking action names against the known actions list
        not_allowed = [
            action.__name__ for action in extra_actions
            if action.__name__ in known_actions
        ]

        if not_allowed:
            msg = ('Cannot use the @action decorator on the following '
                   'methods, as they are existing routes: %s')
            raise ImproperlyConfigured(msg % ', '.join(not_allowed))

        # partition detail and list actions
        detail_actions = [action for action in extra_actions if action.detail]
        list_actions = [action for action in extra_actions if not action.detail]

        routes = []
        for route in self.routes:
            if isinstance(route, DynamicRoute) and route.detail:
                routes += [self._get_dynamic_route(route, action) for action in detail_actions]
            elif isinstance(route, DynamicRoute) and not route.detail:
                routes += [self._get_dynamic_route(route, action) for action in list_actions]
            else:
                routes.append(self._get_root_route(route))

        return routes

    def _get_dynamic_route(self, route, action: ActionMethod):
        initkwargs = route.initkwargs.copy()
        initkwargs['mapping'] = action.mapping

        url_path = _escape_curly_brackets(action.url_path or action.slug)

        assert action.detail is not None, (
            f"@action({action.__name__!r}) missing required argument: 'detail'"
        )

        res = Route(
            url=route.url.replace('{url_path}', url_path),
            mapping=action.mapping or MethodMapper(action, HttpMethod.GET),
            name=route.name.replace('{url_name}', action.url_name or action.slug),
            detail=route.detail,
            initkwargs=initkwargs,
        )

        return res

    def _get_root_route(self, route: Route):
        return route._replace(

        )
    
    def get_method_map(self, viewset: type[View], method_map):
        """
        Given a viewset, and a mapping of http methods to actions,
        return a new mapping which only includes any mappings that
        are actually implemented by the viewset.
        """
        bound_methods = {}

        for method, action in method_map.items():
            if getattr(viewset, action, None) is not None:
                bound_methods[method] = action
        
        return bound_methods

    def get_lookup_regex(self, viewset, lookup_prefix=''):
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
        lookup_field = getattr(viewset, 'lookup_field', 'pk')
        lookup_url_kwarg = getattr(viewset, 'lookup_url_kwarg', None) or lookup_field
        lookup_value = getattr(viewset, 'lookup_value_regex', '[^/.]+')
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
