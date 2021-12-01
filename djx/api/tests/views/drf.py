import typing as t 
from rest_framework.response import Response

from django.http import HttpResponse

from rest_framework import serializers, viewsets

from django_filters.rest_framework.backends import DjangoFilterBackend

from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.routers import DefaultRouter

from djx.iam import UserModel

from . import sample_data_list


router = DefaultRouter()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserModel
        fields = [
            'pk', 'name', 'status', 'role',  'username', 
            'email', 'username'
        ]


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = UserModel.objects.all().order_by('-created_at')
    serializer_class = UserSerializer
    # permission_classes = [permissions.IsAuthenticated]

    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['id', 'name', 'status', 'role', 'email']

    __abc__ = None
    
    @action(detail=True, url_path=r'role/(?P<role>subscriber|affiliate|staff|manager|admin|owner)')
    def role(self, request, *args, role, **kwargs):
        vardump(__user_role__=role)
        return self.retrieve(request, *args, **kwargs)

    # def list(self, request, *args, **kwargs):
    #     # queryset = self.filter_queryset(self.get_queryset())

    #     # page = self.paginate_queryset(queryset)
    #     # if page is not None:
    #     #     serializer = self.get_serializer(data=page, many=True)
    #     #     return self.get_paginated_response(serializer.data)

    #     # serializer = self.get_serializer(data=list(queryset.all()), many=True)
    #     serializer = self.get_serializer(data=sample_data_list, many=True)
    #     serializer.is_valid()
    #     return HttpResponse(sample_data_list, content_type='application/json')


    destroy = None

router.register('users', UserViewSet, 'user')
