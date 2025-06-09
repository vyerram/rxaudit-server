from rest_framework import serializers
from core.serializers import CoreSerializer
from . import models


class Userroleserializer(CoreSerializer):

    class Meta(CoreSerializer.Meta):
        model = models.Userrole
        relations = []


class Userserializer(CoreSerializer):
    pharmacy = serializers.SerializerMethodField()
    volume_group = serializers.SerializerMethodField()

    class Meta(CoreSerializer.Meta):
        model = models.User
        relations = []

    def get_pharmacy(self, obj):
        return super().retrieve_relation_data(obj, "pharmacy")

    def get_volume_group(self, obj):
        return super().retrieve_relation_data(obj, "volume_group")


class RoleAccessControlserializer(CoreSerializer):

    class Meta(CoreSerializer.Meta):
        model = models.RoleAccessControl
        relations = []
