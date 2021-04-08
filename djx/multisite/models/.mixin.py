import logging

from django.db import models
from django.db.models.sql import DeleteQuery, UpdateQuery
from django.db.models.deletion import Collector
from django.db.utils import NotSupportedError

from ..deletion import related_objects
from ..query import wrap_get_compiler, wrap_update_batch, wrap_delete
from ..utils import (
    set_current_site,
    get_current_site,
    get_current_site_value,
    get_site_field,
    get_site_filters,
    get_object_site,
    set_object_site
)


__all__ = [
    'SiteModel',
    'SiteModelMixin',
    'SiteModelManager',
]


logger = logging.getLogger(__name__)




class SiteModelManager(models.Manager):


    def get_queryset(self):
        #Injecting site_id filters in the get_queryset.
        #Injects site_id filter on the current model for all the non-join/join queries. 

        queryset = super().get_queryset()
        current_site = get_current_site()
        if current_site:
            kwargs = get_site_filters(self.model)
            return queryset.filter(**kwargs)
        return queryset


    def bulk_create(self, objs, **kwargs):
        if get_current_site():
            site_value = get_current_site_value()
            for obj in objs:
                set_object_site(obj, site_value)

        return super().bulk_create(objs, **kwargs)




class SiteModelMixin(object):
    #Abstract model which all the models related to site inherit.

    def __init__(self, *args, **kwargs):
        if not hasattr(DeleteQuery.get_compiler, "_sign"):
            DeleteQuery.get_compiler = wrap_get_compiler(DeleteQuery.get_compiler)
            Collector.related_objects = related_objects
            Collector.delete = wrap_delete(Collector.delete)

        if not hasattr(UpdateQuery.get_compiler, "_sign"):
            UpdateQuery.update_batch = wrap_update_batch(UpdateQuery.update_batch)

        super().__init__(*args, **kwargs)

    # def __setattr__(self, attrname, val):

    #     if (attrname in (self.site_field, get_site_field(self).name)
    #         and not self._state.adding
    #         and val
    #         and self.site_value
    #         and val != self.site_value
    #         and val != self.site_object):
    #         self._try_update_site = True

    #     return super(SiteModelMixin, self).__setattr__(attrname, val)

    def _do_update(self, base_qs, using, pk_val, values, update_fields, forced_update):
        #adding site filters for save
        #Citus requires site_id filters for update, hence doing this below change.

        current_site = get_current_site()

        if current_site:
            kwargs = get_site_filters(self.__class__)
            base_qs = base_qs.filter(**kwargs)
        else:
            logger.warning('Attempting to update %s instance "%s" without a current site '
                           'set. This may cause issues in a partitioned environment. '
                           'Recommend calling set_current_site() before performing this '
                           'operation.',
                           self._meta.model.__name__, self)

        return super()._do_update(base_qs, using,
                                                       pk_val, values,
                                                       update_fields,
                                                       forced_update)

    def save(self, *args, **kwargs):
        # if hasattr(self, '_try_update_site'):
        #     raise NotSupportedError('Site column of a row cannot be updated.')

        current_site = get_current_site()
        site_value = get_current_site_value()

        set_object_site(self, site_value)

        if self.site_value and site_value != self.site_value:
            self_site = get_object_site(self)
            set_current_site(self_site)

        try:
            obj = super().save(*args, **kwargs)
        finally:
            set_current_site(current_site)

        return obj

    @property
    def site_field(self):
        return 'site_id'

    @property
    def site_value(self):
        return getattr(self, self.site_field, None)

    @property
    def site_object(self):
        return get_object_site(self)







class SiteModel(SiteModelMixin, models.Model):
    #Abstract model which all the models related to site inherit.

    objects = SiteModelManager()

    class Meta:
        abstract = True
