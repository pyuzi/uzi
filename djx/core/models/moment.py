from django.db.models import DateTimeField


from djx.common.moment import Moment, moment



class MomentField(DateTimeField):

    def to_python(self, value):
        if value is None:
            return value
        elif isinstance(value, Moment):
            return value.datetime
        try:
            return moment.get(value).datetime
        except Exception:
            return super().to_python(value) 
    
    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        elif isinstance(value, Moment):
            return value
        else:
            return moment.get(value)