"""example_project URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.10/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.urls import path, include
# from django.contrib import admin

# from . import views as v


urlpatterns = [
    # path("admin/", admin.site.urls),
    # path('api/', include('djx.api.tests.urls')),
    path('api/contacts/', include('djx.contacts.urls')),
    # path("func/", v.func),
    # path("1/", v.Dj.as_view()),
    # path("2/", v.Djx.as_view()),
    # path("3/", v.Rest.as_view()),
]
