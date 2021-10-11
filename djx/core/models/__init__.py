import sys
import typing as t
from django.apps import apps
from djx.common.proxy import proxy
from djx.common.imports import ImportRef


if t.TYPE_CHECKING:
    from .alias import aliased as aliased
    from . import base as m

else:
    from django.db import models as m


_T_Model = t.TypeVar('_T_Model', bound=m.Model, covariant=True)



from .alias import *
from .fields import *
from . import lookups

from .urn import ModelUrn, ModelUrnValueError, ModelUrnTypeError
from .urn import *


if t.TYPE_CHECKING:
    from .base import Model, Manager, ModelConfig, PolymorphicModel, MPTTModel, PolymorphicMPTTModel
else:

    def _importer(n, m='base'):
        # loc = ImportRef(f'{__package__}.{m}', n)
        loc = ImportRef(f'.{m}', n)
        def resolve():
            rv = loc()
            globals()[n] = rv
            return rv
        return proxy(resolve)

    Model = _importer('Model')
    Manager = _importer('Manager')
    ModelConfig = _importer('ModelConfig')
    PolymorphicModel = _importer('PolymorphicModel')
    MPTTModel = _importer('MPTTModel')
    PolymorphicMPTTModel = _importer('PolymorphicMPTTModel')

    del _importer




def AppModel(app_label: str, model_name: str=None, require_ready: bool=False, *, swapped: bool=True, cache: bool=True):
    pkg: str = None
    if model_name is None:
        try:
            pkg = sys._getframe(1).f_globals.get('__package__')
        except (AttributeError, ValueError):
            pkg = None
        
    def get_model()-> type[_T_Model]:
        model: type[_T_Model]

        if model_name is None:
            al, _, mn = app_label.partition('.')
            if not al and pkg:
                dots = -(len(mn) - len(mn := mn.lstrip('.'))) or len(mn)
                app = apps.get_containing_app_config('.'.join(pkg.split('.')[:dots]))
                model = app.get_model(mn.lower(), require_ready)
            else:
                model = apps.get_model(app_label.lower(), model_name, require_ready)
        else:
            model = apps.get_model(app_label, model_name.lower(), require_ready)

        swap = swapped and model._meta.swapped
        while swap:
            model = apps.get_model(swap, None, require_ready)
            swap = model._meta.swapped

        return model

    return proxy(get_model, cache=cache)



