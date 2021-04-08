import logging

from django.db import models

from flex.utils.decorators import export

from ..settings import (
    SITE_MODEL_IMPL, 
    USER_MODEL_IMPL, 
)



logger = logging.getLogger(__name__)



@export()
class MemberManager(models.Manager):
    
    use_in_migrations = True




@export()
class MemberABC(models.Model):

    objects = MemberManager()

    class Meta:
        abstract = True

    site = models.ForeignKey(SITE_MODEL_IMPL, models.CASCADE, related_name='members')
    user = models.ForeignKey(USER_MODEL_IMPL, models.CASCADE, related_name='memberships')

    is_active = models.BooleanField(blank=True, default=True)
    attrs = models.JSONField(null=True, blank=True, default=None)

    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)

    def __str__(self) -> str:
        return f'{self.user} @ {self.site}'

    


@export()
class Member(MemberABC):

    class Meta:
        swappable = 'MULTISITE_MEMBER_MODEL'






