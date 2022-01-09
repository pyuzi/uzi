
from django.db import models
from django.utils import timezone

# from jani.multisite.fields import SiteForeignKey


class MySite(models.Model):
    pass



class MyMember(models.Model):
    pass



# class MethodManager(SiteManager, PolymorphicManager):
#     pass



# class PayType(models.TextChoices):
#     PAY_IN = 'in'
#     PAY_OUT = 'out'





# class PaymentManager(SiteManager, PolymorphicManager):
#     pass



# class Payment(SiteModel, PolymorphicModel):
 
#     objects = PaymentManager()

#     class Meta:
#         verbose_name = 'payment'

#     uuid = SmallUUIDField(default=uuid_default(), editable=False)
   
#     date = models.DateTimeField(default=timezone.now, help_text="The date on which this payment occurred")

#     description = models.TextField(default="", blank=True)



# class PayIn(Payment):

#     class Meta:
#         proxy = True
#         verbose_name = 'pay in'



# class PayOut(Payment):

#     class Meta:
#         proxy = True
#         verbose_name = 'pay out'


