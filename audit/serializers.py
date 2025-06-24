from rest_framework import serializers
from core.serializers import CoreSerializer
from . import models


class PharmacyAuditDataserializer(CoreSerializer):
    pharmacy = serializers.SerializerMethodField()

    class Meta(CoreSerializer.Meta):
        model = models.PharmacyAuditData
        relations = []

    def get_pharmacy(self, obj):
        return super().retrieve_relation_data(obj, "pharmacy")


class Distributorserializer(CoreSerializer):

    class Meta(CoreSerializer.Meta):
        model = models.Distributors
        relations = []


class DistributorAuditDataserializer(CoreSerializer):
    distributor = serializers.SerializerMethodField()

    class Meta(CoreSerializer.Meta):
        model = models.DistributorAuditData
        relations = []

    def get_distributor(self, obj):
        return super().retrieve_relation_data(obj, "distributor")


class FileDBMappingDataserializer(CoreSerializer):
    # distributor = serializers.SerializerMethodField()
    # pharmacy = serializers.SerializerMethodField()

    class Meta(CoreSerializer.Meta):
        model = models.FileDBMapping
        relations = []

    # def get_distributor(self, obj):
    #     return super().retrieve_relation_data(obj, "distributor")

    # def get_pharmacy(self, obj):
    #     return super().retrieve_relation_data(obj, "pharmacy")


class FileTypeserializer(CoreSerializer):

    class Meta(CoreSerializer.Meta):
        model = models.FileType
        relations = []


class PaymentMethodserializer(CoreSerializer):

    class Meta(CoreSerializer.Meta):
        model = models.PaymentMethod
        relations = []


class ClaimStatusserializer(CoreSerializer):

    class Meta(CoreSerializer.Meta):
        model = models.ClaimStatus
        relations = []


class ProcessLogHdrserializer(CoreSerializer):
    process_log_detail = serializers.SerializerMethodField()

    class Meta(CoreSerializer.Meta):
        model = models.ProcessLogHdr
        relations = []

    def get_process_log_detail(self, obj):
        return super().retrieve_relation_data(obj, "process_log_detail_process_log")


class CleanFilesLogserializer(CoreSerializer):

    class Meta(CoreSerializer.Meta):
        model = models.CleanFilesLog
        relations = []


class ProcessLogDetailserializer(CoreSerializer):
    # file_type = serializers.SerializerMethodField()
    # process_log = serializers.SerializerMethodField()

    class Meta(CoreSerializer.Meta):
        model = models.ProcessLogDetail
        relations = ["file_type", "process_log"]

    # def get_file_type(self, obj):
    #     return super().retrieve_relation_data(obj, "file_type")

    # def get_process_log(self, obj):
    #     return super().retrieve_relation_data(obj, "process_log")


class BinGroupsSerializers(CoreSerializer):
    class Meta(CoreSerializer.Meta):
        model = models.BinGroups
        relations = []


class BinNumbersSerializers(CoreSerializer):
    class Meta(CoreSerializer.Meta):
        model = models.BinNumbers
        relations = []


class ErrorLogserializer(CoreSerializer):

    class Meta(CoreSerializer.Meta):
        model = models.ErrorLogs
        relations = []


class ErrorSeverityserializer(CoreSerializer):

    class Meta(CoreSerializer.Meta):
        model = models.ErrorSeverity
        relations = []
