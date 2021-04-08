import logging
from collections.abc import Mapping

from django.db import models
from django.db.models.base import ModelBase


from flex.utils.decorators import export



from .impl import impl
from ..settings import SITE_MODEL_IMPL




logger = logging.getLogger(__name__)




@export()
class SiteForeignKey(models.ForeignKey):
    '''
    Should be used in place of models.ForeignKey for all foreign key relationships to
    subclasses of SiteModel.

    Adds additional clause to JOINs over this relation to include site_id in the JOIN
    on the SiteModel.

    Adds clause to forward accesses through this field to include site_id in the
    SiteModel lookup.
    '''

    
    def __init__(self, to=None, on_delete=None, related_name=None, related_query_name=None,
                 parent_link=False, to_field=None, blank=True,
                 limit_choices_to=None, db_constraint=True, **kwargs):
        from ..ctx import current_site
        
        kwargs.setdefault('default', current_site)
        
        if isinstance(to, (str, ModelBase)):
            to = to
        else:
            on_delete = on_delete or to
            to = SITE_MODEL_IMPL

        super().__init__(
                to, on_delete, related_name, related_query_name,
                limit_choices_to, parent_link, to_field,
                db_constraint, blank=blank, **kwargs)    
    
    @property
    def _is_site_rel(self) -> bool:
        return self.related_model is impl.Site

    def deconstruct(self):
        from ..ctx import current_site, get_current_site
        name, path, args, kwargs = super().deconstruct()
        
        if kwargs['default'] in (get_current_site, current_site):
            del kwargs['default']

        return name, path, args, kwargs

    # Override
    def get_extra_descriptor_filter(self, instance):
        """
        Return an extra filter condition for related object fetching when
        user does 'instance.fieldname', that is the extra filter is used in
        the descriptor of the field.

        The filter should be either a dict usable in .filter(**kwargs) call or
        a Q-object. The condition will be ANDed together with the relation's
        joining columns.

        A parallel method is get_extra_restriction() which is used in
        JOIN and subquery conditions.
        """
        rv = super().get_extra_descriptor_filter(instance)
        if self._is_site_rel:
            return rv
        if isinstance(rv, dict):
            return self.get_current_site_filter(**rv)
        else:
            return self.get_current_site_filter(rv)

    def get_current_site_filter(self, *args, **kwargs) -> models.Q:
        return impl.Site._default_manager\
            .current_site_filters(self.remote_field.name, *args, **kwargs)
    
   # # Override
    # def get_extra_restriction(self, where_class, alias, related_alias):
    #     """
    #     Return a pair condition used for joining and subquery pushdown. The
    #     condition is something that responds to as_sql(compiler, connection)
    #     method.

    #     Note that currently referring both the 'alias' and 'related_alias'
    #     will not work in some conditions, like subquery pushdown.

    #     A parallel method is get_extra_descriptor_filter() which is used in
    #     instance.fieldname related object fetching.
    #     """

    #     if not (related_alias and alias):
    #         return None

    #     # Fetch site column names for both sides of the relation
    #     lhs_model = self.model
    #     rhs_model = self.related_model
    #     lhs_site_id = get_site_column(lhs_model)
    #     rhs_site_id = get_site_column(rhs_model)

    #     # Fetch site fields for both sides of the relation
    #     lhs_site_field = lhs_model._meta.get_field(lhs_site_id)
    #     rhs_site_field = rhs_model._meta.get_field(rhs_site_id)

    #     # Get references to both site columns
    #     lookup_lhs = lhs_site_field.get_col(related_alias)
    #     lookup_rhs = rhs_site_field.get_col(alias)

    #     # Create "AND lhs.site_id = rhs.site_id" as a new condition
    #     lookup = lhs_site_field.get_lookup('exact')(lookup_lhs, lookup_rhs)
    #     condition = where_class()
    #     condition.add(lookup, 'AND')
    #     return condition




@export()
class SiteOneToOneField(models.OneToOneField, SiteForeignKey):
    # Override
    def __init__(self, *args, **kwargs):
        kwargs['unique'] = False
        super(SiteOneToOneField, self).__init__(*args, **kwargs)









try:
    from mptt.models import TreeForeignKey
except ModuleNotFoundError as e:
    TreeForeignKey = object


@export()
class SiteTreeForeignKey(SiteForeignKey, TreeForeignKey):
    pass






try:
    from polymorphic_tree.models import PolymorphicTreeForeignKey
except ModuleNotFoundError as e:
    PolymorphicTreeForeignKey = object



@export()
class PolymorphicSiteTreeForeignKey(SiteForeignKey, PolymorphicTreeForeignKey):
    pass