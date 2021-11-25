from django_filters import filters

from django_filters.filters import *  # noqa
from django_filters.widgets import BooleanWidget

__all__ = filters.__all__


class BooleanFilter(filters.BooleanFilter):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', BooleanWidget)

        super().__init__(*args, **kwargs)
