import typing as t


from django.db.models.manager import BaseManager
from django.db import models as m


if t.TYPE_CHECKING:
    from .base import Model
    class Manager(m.Manager):

        model: type[Model]
else:
    Manager = m.Manager
    Model = m.Model


""" 
    Patch aliased 
"""
def get_queryset(self: Manager):
    """
    Return a new QuerySet object. Subclasses can override this method to
    customize the behavior of the Manager.
    """
    from .base import Model

    model = self.model
    if issubclass(model, Model):
        return model.__config__._initialize_queryset(self._real_get_queryset(), self)
    
    return self._real_get_queryset()



# def by_natural_key(self: Manager, key):
#     return self.filter(self.model.__config__.natural_key_lookup(key))


# BaseManager.by_natural_key = by_natural_key




def get_by_natural_key(self: Manager, key):
    return self.filter(self.model.__config__.natural_key_lookup(key)).get()
    # return self.by_natural_key(key).get()


BaseManager.get_by_natural_key = get_by_natural_key




BaseManager._real_get_queryset = BaseManager.get_queryset
BaseManager.get_queryset = get_queryset

try:
    from polymorphic.managers import PolymorphicManager
except ImportError:
    PolymorphicManager = None


if PolymorphicManager:
    PolymorphicManager._real_get_queryset = PolymorphicManager.get_queryset
    PolymorphicManager.get_queryset = get_queryset

del get_queryset





# from functools import cache

# from collections import Counter

# from django.db import models as m, transaction

# from django.db import IntegrityError, router

# from django.apps import apps


# from contextvars import ContextVar, copy_context

# from djx.common.moment import moment

# if t.TYPE_CHECKING:
#     from .base import Model
# else:
#     Model = m.Model



# class _DelStack(t.TypedDict):
#     soft: dict[t.Any, Model]
#     hard: dict[t.Any, Model]


# __del_stack = ContextVar[_DelStack]('__del_stack')


# class AbortDeletionException(Exception):
#     ...    


# class SoftDeleteException(AbortDeletionException):
#     ...
    
    
# class DeletionIntegrityError(IntegrityError, AbortDeletionException):
    
#     def __init__(self, objs) -> None:
#         self.objs = objs
#         super().__init__(
#             f"Deleted query contains both 'hard' and 'soft' deleted objects."
#         )





# def __pre_del(sender, instance, **kwds):
#     stack = __del_stack.get(None)

#     if stack:
#         stack['soft' if _can_soft_delete(sender) else 'hard'][instance.pk] = instance
    
    

# def __post_del(sender, instance, **kwds):
#     stack = __del_stack.get(None)
#     if stack:
#         if not stack['soft']:
#             pass
#         elif stack['hard']:
#             raise DeletionIntegrityError(stack)
#         else:
#             raise SoftDeleteException()



# m.signals.pre_delete.connect(__pre_del, dispatch_uid=f'{__name__}.__pre_del')
# m.signals.post_delete.connect(__post_del, dispatch_uid=f'{__name__}.__post_del')


# def delete(self, at=None, *, purge=False):

#     try:
#         # with transaction.atomic():
#         ctx = copy_context()
#         rv = ctx.run(_do_delete, self, at, purge)
#         debug('DELETE RESULT --> ', rv, self)
#         raise IntegrityError('STOP')

#     except DeletionIntegrityError as e:
#         debug('ERRRRRRR -----> ', e.objs)
#     except Exception as e:
#         debug('ERRRRRRR -----> ???? ', e)

        

# def purge(self):
#     ctx = copy_context()
#     return ctx.run(_do_delete, self, None, True)
    


# def _do_delete(self: QuerySet, at=None, purge=False):
#     token = __del_stack.set(None if purge else _DelStack(soft={}, hard={}))
    
#     try:
#         rv = self._real_delete_()
#     except SoftDeleteException as e:
#         stack = __del_stack.get()
        
#         __del_stack.reset(token)
#         token = None

#         if stack['hard']:
#             raise DeletionIntegrityError() from e

#         with transaction.atomic():
#             cnt = Counter()
#             at = at or moment.now()
#             for pk, obj in stack['soft'].items():
#                 assert obj.pk == pk

#                 fields = obj.__class__.__config__.timestamp_fields
#                 if getattr(obj, fields['is_deleted'], False):
#                     continue

#                 setattr(obj, fields['deleted_at'], at)
#                 obj.save(update_fields=[fields['deleted_at']])
#                 cnt[obj.__class__] += 1

#             return sum(cnt.values(), 0), cnt
#     else:
#         __del_stack.reset(token)
#         token = None
#         return rv
#     finally:
#         debug('FINALIZE delete --> XXXXXXXXXXXXXXXXX')
#         token is None or __del_stack.reset(token)
    




# @cache
# def _can_soft_delete(cls):
#     return hasattr(cls, '__config__') \
#         and getattr(cls.__config__, 'soft_deletes', False)





# QuerySet._real_delete_ = QuerySet.delete
# QuerySet.delete = delete
# QuerySet.purge = purge

# del delete
# del purge


# """ 
#     Single object delete
# """

# def delete(self, using=None, keep_parents=False, *, at=None, purge=False):
#     using = using or router.db_for_write(self.__class__, instance=self)
#     assert self.pk is not None, (
#         "%s object can't be deleted because its %s attribute is set to None." %
#         (self._meta.object_name, self._meta.pk.attname)
#     )

#     qs = self.__class__._base_manager\
#             .db_manager(using, hints=dict(instance=self))\
#             .filter(pk=self.pk)
#     return qs.delete(at, purge=purge)


# m.Model._real_delete_ = m.Model.delete
# m.Model.delete = delete

# del delete
