from rest_framework import serializers
from core.serializers import CoreSerializer
from . import models


class Userroleserializer(CoreSerializer):

    class Meta(CoreSerializer.Meta):
        model = models.Userrole
        relations = []


class Userserializer(CoreSerializer):
    # Use PrimaryKeyRelatedField for write operations, SerializerMethodField for read
    pharmacy_display = serializers.SerializerMethodField()
    volume_group_display = serializers.SerializerMethodField()

    class Meta(CoreSerializer.Meta):
        model = models.User
        relations = []
        extra_kwargs = {
            'pharmacy': {'write_only': False, 'required': False, 'allow_null': True},
            'volume_group': {'write_only': False, 'required': False, 'allow_null': True},
        }

    def get_pharmacy_display(self, obj):
        return super().retrieve_relation_data(obj, "pharmacy")

    def get_volume_group_display(self, obj):
        return super().retrieve_relation_data(obj, "volume_group")

    def to_representation(self, instance):
        """Override to return pharmacy/volume_group as objects on read"""
        representation = super().to_representation(instance)
        representation['pharmacy'] = self.get_pharmacy_display(instance)
        representation['volume_group'] = self.get_volume_group_display(instance)
        return representation


class RoleAccessControlserializer(CoreSerializer):

    class Meta(CoreSerializer.Meta):
        model = models.RoleAccessControl
        relations = []
