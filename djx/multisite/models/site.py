
import logging
import re
from typing import Any, ClassVar, Optional, Union, overload

from cachetools.keys import hashkey
from cachetools import TTLCache, cached
from django.db import IntegrityError, models, router, transaction

from flex.utils import text
from flex.utils.decorators import export

from ..settings import (
    MEMBER_MODEL_IMPL, 
    USER_MODEL_IMPL, 
    SITE_CACHE_TLL,
    SITE_CACHE_MAXSIZE,
)




logger = logging.getLogger(__name__)


_sitecache = TTLCache(SITE_CACHE_MAXSIZE, SITE_CACHE_TLL)


def _cache_key(*args):
    def func(self, *a, **kw):
        print(f' - cache key {self.model} {a=}, {kw=}')
        return hashkey(self, *args, *a, **kw)
    return func

    


@export()
def clear_sites_cache(*args, instance=None, using=None, **kwargs) -> None:
    _sitecache.clear()



@export()
class SiteManager(models.Manager):
    
    use_in_migrations = True

    def clear_cache(self) -> None:
        clear_sites_cache()
    
    @cached(_sitecache, _cache_key('get'))
    def get(self, *args: Any, **kwargs: Any):
        print(f' xxxxxx get {self.model} from DB: {args=}, {kwargs=} xxxxxx')
        return super().get(*args, **kwargs)

    @cached(_sitecache, _cache_key('get_all'))
    def get_all(self, *args: Any, **kwargs: Any):
        print(f' xxxxxx get_all {self.model} from DB: {args=}, {kwargs=} xxxxxx')
        return list((self.filter(*args, **kwargs)))

    def get_current(self):
        return next(self.get_all_current(), None)
    
    def get_all_current(self):
        from ..ctx import get_all_current_site_pks
        for pk in get_all_current_site_pks():
            if pk and (yv := self.get(pk=pk)):
                yield yv

    def get_by_natural_key(self, slug):
        return self.get(slug=slug)

    def current_site_filters(self, field='site', *args, **extra) -> models.Q:
        if sites := tuple(self.get_all_current()):
            extra[f'{field}__in'] = sites
        return models.Q(*args, **extra)
    




@export()
class SiteABC(models.Model):

    objects: ClassVar[SiteManager] = SiteManager()

    class Meta:
        abstract = True

    name = models.CharField(max_length=128) 
    slug = models.SlugField(max_length=128, unique=True)
    is_active = models.BooleanField(blank=True, default=True)
    attrs = models.JSONField(null=True, blank=True, default=None)

    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)

    owner = models.ForeignKey(USER_MODEL_IMPL, models.CASCADE, related_name='own_sites', null=True, blank=True)
    users = models.ManyToManyField(USER_MODEL_IMPL, related_name='sites', through=MEMBER_MODEL_IMPL)

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs) -> None:
        self.slug = self.slugify(self.slug or self.name)

        # Make sure we write to the same db for all attempted writes,
        # with a multi-master setup, theoretically we could try to
        # write and rollback on different DBs
        kwargs["using"] = using = kwargs.get("using") or router.db_for_write(
            type(self), instance=self
        )
        # Be opportunistic and try to save the tag, this should work for
        # most cases ;)
        try:
            with transaction.atomic(using=using):
                super().save(*args, **kwargs)
        except IntegrityError as e:
            # Now try to find existing slugs with similar names
            slugs = set(self._get_similar_slugs().using(using))
            if not slugs:
                raise e

            i = len(slugs)
            while True:
                slug = self.slugify(self.slug, i)
                if slug not in slugs:
                    self.slug = slug
                    break
                i += 1
            return super().save(*args, **kwargs)
   
    def _get_similar_slugs(self, qs=None):
        return self._similar_slugs_query(qs).values_list('slug', flat=True)
        
    def _similar_slugs_query(self, queryset=None):
        return (queryset or self._default_manager)\
            .filter(slug__startswith=self.slug)

    @classmethod
    def slugify(cls, tag, i=None):
        return f"{text.slug(tag)}{cls._get_slug_suffix(i)}"
    
    @classmethod
    def _get_slug_suffix(cls, i: Optional[Any]) -> str:
        return f'_{str(i).rjust(3, "0")}' if i or i == 0 else ''



@export()
class Site(SiteABC):

    class Meta:
        swappable = 'MULTISITE_SITE_MODEL'




