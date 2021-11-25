import typing as t 


from djx.schemas import OrmSchema, EmailStr, Schema, constr

from djx.common import moment


from djx.iam import UserModel, UserRole, UserStatus

from djx.api import  mixins



from djx.api.routers import DefaultRouter

router = DefaultRouter()


class UserIn(Schema):
    name: str
    role: UserRole = UserRole.SUBSCRIBER
    email: EmailStr
    password: constr(min_length=5)

    # phone: str



class UserOut(OrmSchema):
    pk: int
    name: str
    status: UserStatus
    role: UserRole
    email: str
    username: str
    # created_at: moment.Moment



class UsersView(mixins.CrudModelMixin):

    # __slots__ = ()

    class Config:
        queryset = UserModel.objects.order_by('created_at')
        request_schema = UserIn
        response_schema = UserOut


router.register('users', UsersView)