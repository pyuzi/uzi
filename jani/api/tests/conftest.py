import pytest
import typing as t

from django.conf import settings

# @pytest.fixture(autouse=True)
# def use_dummy_cache_backend(settings):
#     settings.RO = {
#         "default": {
#             "BACKEND": "django.core.cache.backends.dummy.DummyCache",
#         }
#     }