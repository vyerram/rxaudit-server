from rest_framework import serializers
from core.serializers import CoreSerializer
from core.utils import get_s3_file_location
from person.serializers import Addressserializer, Personserializer
from . import models
from core.utils import is_str_empty_or_none


class Groupserializer(CoreSerializer):

    class Meta(CoreSerializer.Meta):
        model = models.Group
        relations = []


class VolumeGroupserializer(CoreSerializer):
    group = serializers.SerializerMethodField()

    class Meta(CoreSerializer.Meta):
        model = models.VolumeGroup
        relations = []

    def get_group(self, obj):
        return super().retrieve_relation_data(obj, "group")


class VolumeGroupSalesInfoserializer(CoreSerializer):
    volumegroup = serializers.SerializerMethodField()
    pharmacy = serializers.SerializerMethodField()

    class Meta(CoreSerializer.Meta):
        model = models.VolumeGroupSalesInfo
        relations = []

    def get_pharmacy(self, obj):
        if obj and obj.volumegroup:
            pharma_list = [
                rec
                for rec in obj.volumegroup.pharmacy_volumegroup_id.all().values(
                    "id", "dba", "corp_name", "sap_ship_to_no"
                )
            ]
            return pharma_list
        return None

    def get_volumegroup(self, obj):
        return super().retrieve_relation_data(obj, "volumegroup")


class GroupSalesInfoserializer(CoreSerializer):
    group = serializers.SerializerMethodField()

    class Meta(CoreSerializer.Meta):
        model = models.GroupSalesInfo
        relations = []

    def get_group(self, obj):
        return super().retrieve_relation_data(obj, "group")


class PharmacyStatusserializer(CoreSerializer):

    class Meta(CoreSerializer.Meta):
        model = models.PharmacyStatus
        relations = []


class PharmacySoftwareserializer(CoreSerializer):

    class Meta(CoreSerializer.Meta):
        model = models.PharmacySoftware
        relations = []


class Pharmacyserializer(CoreSerializer):
    address = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    sales_contact = serializers.SerializerMethodField()
    volume_group = serializers.SerializerMethodField()

    class Meta(CoreSerializer.Meta):
        model = models.Pharmacy
        relations = []

    def get_address(self, obj):
        return super().retrieve_relation_data(obj, "address")

    def get_status(self, obj):
        return super().retrieve_relation_data(obj, "status")

    def get_sales_contact(self, obj):
        return super().retrieve_relation_data(obj, "sales_contact")

    def get_volume_group(self, obj):
        return super().retrieve_relation_data(obj, "volume_group")


class PharmacySalesInfoserializer(CoreSerializer):
    pharmacy = serializers.SerializerMethodField()

    class Meta(CoreSerializer.Meta):
        model = models.PharmacySalesInfo
        relations = []

    def get_pharmacy(self, obj):
        return super().retrieve_relation_data(obj, "pharmacy")


class RebateInfoserializer(CoreSerializer):
    pharmacy = serializers.SerializerMethodField()

    class Meta(CoreSerializer.Meta):
        model = models.RebateInfo
        relations = []

    def get_pharmacy(self, obj):
        return super().retrieve_relation_data(obj, "pharmacy")


class FileProcessingLogsserializer(CoreSerializer):
    file_link = serializers.SerializerMethodField()

    class Meta(CoreSerializer.Meta):
        model = models.FileProcessingLogs
        relations = []

    def get_file_link(self, obj):
        if (
            obj.file_location
            and is_str_empty_or_none(obj.file_location.strip())
            and "/" in obj.file_location
        ):
            bucket, object_name = obj.file_location.split("/")
            return get_s3_file_location(bucket, object_name)
        else:
            return ""


class ProcessingStatusserializer(CoreSerializer):

    class Meta(CoreSerializer.Meta):
        model = models.ProcessingStatus
        relations = []
