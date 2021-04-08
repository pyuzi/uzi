from django.contrib import admin

from .models import impl


@admin.register(impl.Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = [
        "pk",
        "name",
        "slug",
        "owner",
        "is_active",
        # "created_at",
        # "updated_at",
    ]


@admin.register(impl.Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = [
        "pk",
        "__str__",
        "is_active",
        # "created_at",
        # "updated_at",
    ]


