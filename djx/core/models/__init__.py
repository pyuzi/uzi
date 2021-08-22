from . import _patch as __

import typing as t
from django.apps import apps
from djx.common.proxy import proxy


if t.TYPE_CHECKING:
    from .alias import _aliased as aliased
    from . import base as m
else:
    from .alias import aliased
    from django.db import models as m



from .fields import *
from . import lookups

from .urn import ModelUrn, ModelUrnValueError, ModelUrnTypeError
from .urn import *





def AppModel(app_label, model_name=None, require_ready=True, *, swapped: bool=True):
    def get_model()-> type[m.Model]:
        rv: type[m.Model] = apps.get_model(app_label, model_name, require_ready)
        if swapped:
            while (_swapped := rv._meta.swapped):
                rv = apps.get_model(_swapped, None, require_ready)
        return rv

    return proxy(get_model, cache=True)

