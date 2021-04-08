from django.conf import settings

from flex.utils.data import setdefault


APP_NAMESPACE = "djx.multisite"

SITE_COOKIE_NAME = getattr(settings, 'SITE_COOKIE_NAME', 'site_id')
SITE_MODEL_NAME = getattr(settings, 'SITE_MODEL_NAME', None)

CITUS_EXTENSION_INSTALLED = getattr(settings, 'CITUS_EXTENSION_INSTALLED', False)

USER_MODEL_IMPL = getattr(settings, 'AUTH_USER_MODEL', 'auth.User')
SITE_MODEL_IMPL = setdefault(settings, 'MULTISITE_SITE_MODEL', 'multisite.Site')
MEMBER_MODEL_IMPL = setdefault(settings, 'MULTISITE_MEMBER_MODEL', 'multisite.Member')


SITE_CACHE_TLL = setdefault(settings, 'SITE_CACHE_TLL', 600)
SITE_CACHE_MAXSIZE = setdefault(settings, 'SITE_CACHE_MAXSIZE', 1024)
