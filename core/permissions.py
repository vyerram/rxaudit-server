from rest_framework.permissions import BasePermission
from users.constants import AccessType
from django.core.cache import cache
from http import HTTPMethod


class CheckFunctionalAccess(BasePermission):
    """
    Checks wether user has permission to access specific entity.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.access_data = cache.get("access_data")
        self.write_methods = [
            HTTPMethod.PUT.value,
            HTTPMethod.POST.value,
            HTTPMethod.DELETE.value,
            HTTPMethod.PATCH.value,
        ]

    # TO-DO : Need to implement Last 3 and Encrypt
    def get_permissions_for_action(self, role, view_name, request_method):
        if self.access_data and view_name in self.access_data:
            access_type = self.access_data[role][view_name]
            if AccessType.FULL.value == access_type:
                return True
            elif AccessType.READ.value == access_type:
                if request_method in self.write_methods:
                    return False
                return True
            return False
        return True

    def has_permission(self, request, view):
        if request.user and request.user.is_authenticated:
            return self.get_permissions_for_action(
                request.user.role.name, view.basename, request.method
            )
