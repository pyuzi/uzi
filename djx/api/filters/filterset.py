from copy import deepcopy

from django.db import models
from django.utils.translation import gettext_lazy as _

from django_filters import filterset

from .filters import BooleanFilter, IsoDateTimeFilter

FILTER_FOR_DBFIELD_DEFAULTS = deepcopy(filterset.FILTER_FOR_DBFIELD_DEFAULTS)
FILTER_FOR_DBFIELD_DEFAULTS.update({
    models.DateTimeField: {'filter_class': IsoDateTimeFilter},
    models.BooleanField: {'filter_class': BooleanFilter},
    models.NullBooleanField: {'filter_class': BooleanFilter},
})


class FilterSet(filterset.FilterSet):
    FILTER_DEFAULTS = FILTER_FOR_DBFIELD_DEFAULTS

