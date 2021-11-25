import typing as t 
from rest_framework.response import Response


from rest_framework import viewsets
from rest_framework import serializers

from django_filters.rest_framework.backends import DjangoFilterBackend
from rest_framework.routers import DefaultRouter

router = DefaultRouter()



from djx.iam import UserModel

from . import sample_data_list


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserModel
        fields = [
            'pk', 'name', 'status', 'role',  'username', 
            'email', 'username'
        ]




class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = UserModel.objects.all().order_by('-created_at')
    serializer_class = UserSerializer
    # permission_classes = [permissions.IsAuthenticated]

    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['id', 'name', 'status', 'role', 'email']
    
    # def list(self, request, *args, **kwargs):
    #     # queryset = self.filter_queryset(self.get_queryset())

    #     # page = self.paginate_queryset(queryset)
    #     # if page is not None:
    #     #     serializer = self.get_serializer(data=page, many=True)
    #     #     return self.get_paginated_response(serializer.data)

    #     # serializer = self.get_serializer(data=list(queryset.all()), many=True)
    #     serializer = self.get_serializer(data=sample_data_list, many=True)
    #     serializer.is_valid()
    #     return Response(serializer.data)


router.register('users', UserViewSet, 'user')
