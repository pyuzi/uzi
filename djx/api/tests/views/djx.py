import typing as t
from djx.api.types import HttpMethod 

from djx.schemas import OrmSchema, EmailStr, Schema, constr

from djx.common import moment

from djx.iam import UserModel, UserRole, UserStatus
from djx.api.views import  mixins, generic, action
from djx.api.filters.backends import  DjangoFilterBackend

from djx.api.routers import DefaultRouter

from . import sample_data_list


router = DefaultRouter()


class UserIn(Schema):
    name: str
    role: UserRole = UserRole.SUBSCRIBER
    status: UserStatus = UserStatus.PENDING

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


class UsersViewMix(mixins.CrudModelMixin):

    __slots__ = ('suffix', 'basename', 'detail')

    class Config:
        queryset = UserModel.objects.all().order_by('created_at')
        request_schema = UserIn
        response_schema = UserOut
        filter_pipes = [DjangoFilterBackend]
        filterset_fields = ['id', 'name', 'status', 'role', 'email']


    # @action(http_methods=HttpMethod.GET, multi_response=True)
    # def list(self):
    #     return mixins.Response(sample_data_list, content_type = 'application/json')


#     @property
    # def objects(self):
    #     """
    #     The list of filtered items for this view.
        
    #     This must be an iterable, and may be a queryset.
    #     Override `self._get_objects()`.

    #     """
    #     return sample_data_list


class UsersView(generic.RestModelView):

    __slots__ = ('suffix', 'basename', 'detail')

    class Config:
        queryset = UserModel.objects.all().order_by('created_at')
        request_schema = UserIn
        response_schema = UserOut
        filter_pipes = [DjangoFilterBackend]
        filterset_fields = ['id', 'name', 'status', 'role', 'email']

    @action(detail=False)
    def groups(self, *args, **kwds):
        self.object

    # put = delete = None

    

router.register('users', UsersView, 'user')
# router.register('users', UsersViewMix, 'user')
# router.register('users-rest', UsersView, 'user')