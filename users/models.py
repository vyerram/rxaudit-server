from django.db import models

from core.models import CoreModel, CoreLookupModel
from pharmacy.models import Pharmacy, VolumeGroup
from django.contrib.auth.models import AbstractUser
import uuid


class Userrole(CoreModel):
    name = models.CharField(db_column="url_name", max_length=128)
    code = models.CharField(db_column="url_code", max_length=128)

    class Meta:
        db_table = "SET_URL_UserRole"


class User(AbstractUser, CoreModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    otp = models.CharField(max_length=4, blank=True, null=True)
    role = models.ForeignKey(
        Userrole,
        on_delete=models.PROTECT,
        db_column="usr_userrole",
        related_name="userrole_user_user_id",
        to_field="id",
    )
    pharmacy = models.ForeignKey(
        Pharmacy,
        on_delete=models.PROTECT,
        db_column="usr_pharmacy",
        related_name="+",
        to_field="id",
        blank=True,
        null=True,
    )
    volume_group = models.ForeignKey(
        VolumeGroup,
        on_delete=models.PROTECT,
        db_column="usr_volume_group",
        related_name="+",
        to_field="id",
        blank=True,
        null=True,
    )

    def __str__(self):
        if self.first_name or self.last_name:
            return self.first_name + " " + self.last_name
        else:
            return self.username

    class Meta:
        db_table = "SET_USR_User"


class AccessControlType(CoreLookupModel):
    class Meta:
        db_table = "SET_ACT_AccessControlType"


class AccessControl(CoreModel):
    access_name = models.CharField(db_column="acp_access_name", max_length=128)
    access_control_type = models.ForeignKey(
        AccessControlType,
        db_column="acp_access_control_type",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "SET_ACP_AccessControl"


class AccessType(CoreLookupModel):
    class Meta:
        db_table = "SET_AST_AccessType"


class RoleAccessControl(CoreModel):
    role = models.ForeignKey(
        Userrole,
        db_column="rac_role",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )
    access_control = models.ForeignKey(
        AccessControl,
        db_column="rac_access_control",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )
    access_type = models.ForeignKey(
        AccessType,
        db_column="rac_access_type",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "SET_RAC_RoleAccessControl"


class UserAccessControl(CoreModel):
    user = models.ForeignKey(
        User,
        db_column="uac_user",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )
    access_control = models.ForeignKey(
        AccessControl,
        db_column="uac_access_control",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )
    access_type = models.ForeignKey(
        AccessType,
        db_column="uac_access_type",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "SET_UAC_UserAccessControl"
