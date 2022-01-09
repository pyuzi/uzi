
from .settings import *


# Application definition

# INSTALLED_APPS = [
#     "django.contrib.auth",
#     "django.contrib.contenttypes",
#     "django.contrib.sessions",
#     "django_extensions",
#     "example_app",
# ]

# MIDDLEWARE = [
#     # "django.middleware.security.SecurityMiddleware",
#     # "django.contrib.sessions.middleware.SessionMiddleware",
#     # "django.middleware.common.CommonMiddleware",
#     # "django.middleware.csrf.CsrfViewMiddleware",
#     # "django.contrib.auth.middleware.AuthenticationMiddleware",
# ]

LOGGING_LEVEL = 'INFO'

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] [{levelname}]: {message} ({module})",
            "style": "{",
        },
        "simple": {
            "format": "[{asctime}] [{levelname}]: {message} ({module})",
            "style": "{",
        },
    },
    "filters": {"require_debug_true": {"()": "django.utils.log.RequireDebugTrue"}},
    "handlers": {
        "console": {
            "level": "DEBUG",
            # 'filters': ['require_debug_true'],
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "mail_admins": {
            "level": "ERROR",
            "class": "django.utils.log.AdminEmailHandler",
            # 'filters': ['special']
        },
    },
    "loggers": {
        "": {"handlers": ["console"], "level": "DEBUG", "propagate": True},
        "django": {"handlers": ["console"], "level": LOGGING_LEVEL, "propagate": False},
        "django.request": {
            "handlers": ["console", "mail_admins"],
            "level": LOGGING_LEVEL,
            "propagate": False,
        },
        "django.utils.autoreload": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "jani": {
            "handlers": ["console", "mail_admins"],
            "level": "DEBUG",
            "propagate": True,
        },
    },
}


try:
    from .local_settings import *
except ModuleNotFoundError:
    pass