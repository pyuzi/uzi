import typing as t 


from rest_framework import viewsets
from rest_framework import serializers


from rest_framework.routers import DefaultRouter

router = DefaultRouter()



from djx.iam import UserModel



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


router.register('users', UserViewSet)
