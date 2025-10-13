

from audit.models import ErrorLogs
import json
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
    failed_files = serializers.SerializerMethodField()

    class Meta(CoreSerializer.Meta):
        model = models.ProcessLogHdr
        relations = []

    def get_process_log_detail(self, obj):
        return super().retrieve_relation_data(obj, "process_log_detail_process_log")
    
    def get_failed_files(self, obj):
        """
        Collects failed filenames from JSON field or from ErrorLogs if JSON not populated.
        """
        # ✅ Preferred: use JSON field if present
        if hasattr(obj, "failed_files_json") and obj.failed_files_json:
            try:
                return json.loads(obj.failed_files_json)
            except Exception:
                return []

        # ✅ Fallback: infer failed filenames from ErrorLogs messages

        logs = ErrorLogs.objects.filter(process_log=obj).values_list("error_message", flat=True)
        failed_files = []
        for msg in logs:
            if " in " in msg and any(ext in msg for ext in [".xlsx", ".xls", ".csv"]):
                candidate = msg.split(" in ")[-1].split()[0].strip()
                if candidate not in failed_files:
                    failed_files.append(candidate)
        return failed_files

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
