from django.db import IntegrityError
from core.views import CoreViewset
from . import models, serializers
from .constants import UserRoleCodes, user_signup_template
from django.core.mail import EmailMessage
from django.conf import settings
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.hashers import make_password


class Userroleviewset(CoreViewset):
    serializer_class = serializers.Userroleserializer
    queryset = models.Userrole.objects.all()


class RoleAccessControlviewset(CoreViewset):
    serializer_class = serializers.RoleAccessControlserializer
    queryset = models.RoleAccessControl.objects.select_related(
        "role", "access_control", "access_type"
    ).all()


class Userviewset(CoreViewset):
    serializer_class = serializers.Userserializer
    queryset = models.User.objects.select_related("role").all()

    def create(self, request, *args, **kwargs):
        try:
            data = request.data
            role = models.Userrole.objects.filter(id=data["role"])
            pharmacy_user_role = models.Userrole.objects.get(
                code=UserRoleCodes.PharmacyUser.value
            )
            volume_user_role = models.Userrole.objects.get(
                code=UserRoleCodes.VolumeUser.value
            )
            pharmacy = None
            volume_group = None
            if not role or len(role) == 0:
                return Response(
                    status=status.HTTP_400_BAD_REQUEST,
                    data={"message": "Need Valid Role to save User"},
                )
            else:
                role = role.last()
                if role == pharmacy_user_role:
                    if "pharmacy" in data:
                        pharmacy = models.Pharmacy.objects.filter(id=data["pharmacy"])
                        if not pharmacy or len(pharmacy) == 0:
                            return Response(
                                status=status.HTTP_400_BAD_REQUEST,
                                data={"message": "Need Valid Pharmacy to save User"},
                            )
                    else:
                        return Response(
                            status=status.HTTP_400_BAD_REQUEST,
                            data={"message": "Need Valid Pharmacy to save User"},
                        )
                    pharmacy = pharmacy.last()
                if volume_user_role == role:
                    if "volume_group" in data:
                        volume_group = models.VolumeGroup.objects.filter(
                            id=data["volume_group"]
                        )
                        if not volume_group or len(volume_group) == 0:
                            return Response(
                                status=status.HTTP_400_BAD_REQUEST,
                                data={
                                    "message": "Need Valid Volume group to save User"
                                },
                            )
                    else:
                        return Response(
                            status=status.HTTP_400_BAD_REQUEST,
                            data={"message": "Need Valid Volume group to save User"},
                        )
                    volume_group = volume_group.last()

            user = models.User.objects.create_user(
                username=data["username"],
                email=data["email"],
                role=role,
                pharmacy=pharmacy,
                volume_group=volume_group,
                password=data["password"],
            )
            token, created = Token.objects.get_or_create(user=request.user)
            link = f"{settings.HOST_URL}/login"
            email = EmailMessage(
                "Invite from AllwinRX",
                user_signup_template % (link, user.username, data["password"]),
                settings.EMAIL_HOST_USER,
                [user.email],
            )
            email.send()
            user_obj = serializers.Userserializer(user, many=False)
            return Response(
                status=status.HTTP_200_OK,
                data=user_obj.data,
            )
        except IntegrityError:
            return Response(
                status=status.HTTP_409_CONFLICT, data="DuplicateRecord exists"
            )
        except Exception as e:
            raise e

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        data = request.data
        data["password"] = make_password(data["password"])
        serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, "_prefetched_objects_cache", None):
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)
