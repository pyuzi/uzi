from django.core import checks
from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.db.models import Q

from flex.utils.decorators import export

from .impl import impl


@export()
class CurrentSiteManager(models.Manager):
    "Use this to limit objects to those associated with the current site."

    use_in_migrations = True

    def __init__(self, field_name=None):
        super().__init__()
        self.__field_name = field_name

    def check(self, **kwargs):
        errors = super().check(**kwargs)
        errors.extend(self._check_field_name())
        return errors

    def _check_field_name(self):
        field_name = self._get_field_name()
        try:
            field = self.model._meta.get_field(field_name)
        except FieldDoesNotExist:
            return [
                checks.Error(
                    "CurrentSiteManager could not find a field named '%s'." % field_name,
                    obj=self,
                    id='sites.E001',
                )
            ]

        if not field.many_to_many and not isinstance(field, (models.ForeignKey)):
            return [
                checks.Error(
                    "CurrentSiteManager cannot use '%s.%s' as it is not a foreign key or a many-to-many field." % (
                        self.model._meta.object_name, field_name
                    ),
                    obj=self,
                    id='sites.E002',
                )
            ]

        return []

    def _get_field_name(self):
        """ Return self.__field_name or 'site' or 'sites'. """

        if not self.__field_name:
            try:
                self.model._meta.get_field('site')
            except FieldDoesNotExist:
                self.__field_name = 'sites'
            else:
                self.__field_name = 'site'
        return self.__field_name
    
    def Q(self, **extra) -> Q:
        return impl.Site._default_manager\
            .current_site_filters(self._get_field_name(), **extra)

    def get_queryset(self):
        return super().get_queryset().filter(self.Q())



