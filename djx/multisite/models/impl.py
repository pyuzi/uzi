
from typing import Type, Union
from django.apps import apps
from django.db.models.base import Model


from ..settings import SITE_MODEL_IMPL, MEMBER_MODEL_IMPL


__all__ = [
    'impl',
]

class _ModelsImpl:

    @property
    def Site(self) -> Union[Type[Model]]:
        return apps.get_model(SITE_MODEL_IMPL)

    @property
    def Member(self) -> Union[Type[Model]]:
        return apps.get_model(MEMBER_MODEL_IMPL)

    
    
impl = _ModelsImpl()

