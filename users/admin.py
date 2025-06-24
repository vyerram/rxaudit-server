from django.contrib.auth.admin import UserAdmin

from django.contrib import admin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    add_fieldsets = UserAdmin.add_fieldsets
