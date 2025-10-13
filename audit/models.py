from django.db import models
from core.models import CoreModel, CoreLookupModel
from pharmacy.models import Pharmacy, ProcessingStatus, PharmacySoftware


class FileType(CoreLookupModel):

    class Meta:
        db_table = "CFG_FTP_FileType"


class PaymentMethod(CoreLookupModel):

    class Meta:
        db_table = "CFG_PYM_PAYMENTMETHOD"


class ClaimStatus(CoreLookupModel):

    class Meta:
        db_table = "CFG_CMS_CLAIMSTATUS"


class ErrorSeverity(CoreLookupModel):

    class Meta:
        db_table = "CFG_ERS_ErrorSeverity"


class ProcessLogHdr(CoreModel):
    name = models.CharField(db_column="plg_name", max_length=128)
    status = models.ForeignKey(
        ProcessingStatus,
        on_delete=models.PROTECT,
        related_name="+",
        db_column="plg_status",
        to_field="id",
        blank=True,
        null=True,
    )
    log = models.TextField(db_column="plg_log", blank=True, null=True)
    output_file = models.CharField(
        db_column="plg_output_file", max_length=512, blank=True, null=True
    )
    payment_method = models.ManyToManyField(
        PaymentMethod, db_column="plg_payment_method", related_name="+", blank=True
    )
    claim_status = models.ManyToManyField(
        ClaimStatus, db_column="plg_claim_status", related_name="+", blank=True
    )
    pharmacy_from_date = models.DateField(
        db_column="plg_pharmacy_from_date", blank=True, null=True
    )
    pharmacy_to_date = models.DateField(
        db_column="plg_pharmacy_to_date", blank=True, null=True
    )
    distributor_from_date = models.DateField(
        db_column="plg_distributor_from_date", blank=True, null=True
    )
    distributor_to_date = models.DateField(
        db_column="plg_distributor_to_date", blank=True, null=True
    )
    group = models.CharField(
        db_column="plg_group", blank=True, null=True, max_length=128
    )
    pcn = models.CharField(db_column="plg_pcn", blank=True, null=True, max_length=128)

    bin_number = models.CharField(
        db_column="plg_bin_number", blank=True, null=True, max_length=128
    )
    processed_count = models.IntegerField(db_column="plg_processed_count", blank=True, null=True)
    failed_count = models.IntegerField(db_column="plg_failed_count", blank=True, null=True)
    failed_files_json = models.JSONField(db_column="plg_failed_files", blank=True, null=True)

    class Meta:
        db_table = "OPT_PLG_ProcessLogHdr"

    def __str__(self):
        return self.name


class CleanFilesLog(CoreModel):
    name = models.CharField(db_column="cfl_name", max_length=128)
    status = models.ForeignKey(
        ProcessingStatus,
        on_delete=models.PROTECT,
        related_name="+",
        db_column="cfl_status",
        to_field="id",
        blank=True,
        null=True,
    )
    input_file_name = models.CharField(
        db_column="cfl_input_file_name", max_length=256, blank=True, null=True
    )
    input_file_url = models.CharField(
        db_column="cfl_input_file_url", max_length=512, blank=True, null=True
    )
    output_file_url = models.CharField(
        db_column="cfl_output_file_url", max_length=512, blank=True, null=True
    )
    log = models.TextField(db_column="plg_log", blank=True, null=True)

    class Meta:
        db_table = "OPT_CFL_CleanFilesLog"


class ProcessLogDetail(CoreModel):
    file_type = models.ForeignKey(
        FileType,
        on_delete=models.PROTECT,
        db_column="plg_file_type",
        related_name="process_log_file_type",
        blank=True,
        null=True,
        to_field="id",
    )
    file_name = models.CharField(db_column="plg_file_name", max_length=256)
    file_url = models.CharField(db_column="plg_file_url", max_length=512)

    process_log = models.ForeignKey(
        ProcessLogHdr,
        on_delete=models.PROTECT,
        db_column="dad_process_log_id",
        related_name="process_log_detail_process_log",
        blank=True,
        null=True,
        to_field="id",
    )

    distributor = models.ForeignKey(
        "Distributors",
        on_delete=models.PROTECT,
        db_column="dad_distributor",
        related_name="process_log_detail_distributor",
        blank=True,
        null=True,
        to_field="id",
    )
    pharmacy = models.ForeignKey(
        Pharmacy,
        on_delete=models.PROTECT,
        db_column="dad_pharmacy",
        related_name="process_log_detail_pharmacy",
        blank=True,
        null=True,
        to_field="id",
    )

    class Meta:
        db_table = "OPT_PLG_ProcessLogDetail"


class PharmacyAuditData(CoreModel):
    ndc = models.CharField(db_column="pad_ndc", max_length=40)
    date = models.DateField(db_column="pad_date", blank=True, null=True)
    brand = models.CharField(
        db_column="pad_brand", blank=True, null=True, max_length=128
    )
    strength = models.CharField(
        db_column="pad_strength", blank=True, null=True, max_length=128
    )
    unit_size = models.CharField(
        db_column="pad_size", blank=True, null=True, max_length=128
    )
    quantity = models.FloatField(db_column="pad_quantity")
    drug_name = models.CharField(
        db_column="pad_drug_name", max_length=512, blank=True, null=True
    )
    ins_paid = models.FloatField(db_column="pad_ins_paid", blank=True, null=True)
    ins_bin_number = models.FloatField(
        db_column="pad_ins_bin_number", blank=True, null=True
    )
    patient_copay = models.FloatField(
        db_column="pad_patient_copay", blank=True, null=True
    )
    claim_status = models.CharField(
        db_column="pad_claim_status", blank=True, null=True, max_length=128
    )
    payment_option = models.CharField(
        db_column="pad_payment_option", blank=True, null=True, max_length=128
    )
    group = models.CharField(
        db_column="pad_group", blank=True, null=True, max_length=128
    )
    pcn = models.CharField(db_column="pad_pcn", blank=True, null=True, max_length=128)
    pharmacy = models.ForeignKey(
        Pharmacy,
        on_delete=models.PROTECT,
        db_column="pad_pharmacy",
        related_name="pharmacy_pharmacyaudit",
        blank=True,
        null=True,
        to_field="id",
    )
    process_log = models.ForeignKey(
        ProcessLogHdr,
        on_delete=models.PROTECT,
        db_column="pad_process_log_id",
        related_name="pharmacy_process_log",
        blank=True,
        null=True,
        to_field="id",
    )

    class Meta:
        db_table = "OPT_PAD_PharmacyAuditData"


class Distributors(CoreLookupModel):
    class Meta:
        db_table = "OPT_DTB_Distributors"


class DistributorAuditData(CoreModel):
    ndc = models.CharField(db_column="dad_ndc", max_length=40)
    drug_name = models.CharField(
        db_column="dad_drug_name", blank=True, null=True, max_length=128
    )
    quantity = models.FloatField(db_column="dad_quantity")
    date = models.DateField(db_column="dad_date", blank=True, null=True)
    distributor = models.ForeignKey(
        Distributors,
        on_delete=models.PROTECT,
        db_column="dad_distributor",
        related_name="distributor_distributor_audit_data",
        blank=True,
        null=True,
        to_field="id",
    )
    process_log = models.ForeignKey(
        ProcessLogHdr,
        on_delete=models.PROTECT,
        db_column="dad_process_log_id",
        related_name="distributor_process_log",
        blank=True,
        null=True,
        to_field="id",
    )

    class Meta:
        db_table = "OPT_DAD_DistributorAuditData"


class FileDBMapping(CoreModel):
    source_col_name = models.CharField(db_column="fmp_source_col_name", max_length=128)
    dest_col_name = models.CharField(db_column="fmp_dest_col_name", max_length=128)
    date_type = models.CharField(db_column="fmp_date_type", blank=True, null=True)
    distributor = models.ForeignKey(
        Distributors,
        on_delete=models.PROTECT,
        db_column="fmp_distributor",
        related_name="distributor_file_db_mapping",
        blank=True,
        null=True,
        to_field="id",
    )
    pharmacy = models.ForeignKey(
        Pharmacy,
        on_delete=models.PROTECT,
        db_column="fmp_pharmacy",
        related_name="pharmacy_file_db_mapping",
        blank=True,
        null=True,
        to_field="id",
    )

    file_type = models.ForeignKey(
        FileType,
        on_delete=models.PROTECT,
        db_column="fmp_file_type",
        related_name="file_db_mapping_file_type",
        blank=True,
        null=True,
        to_field="id",
    )
    pharmacy_software = models.ForeignKey(
        PharmacySoftware,
        on_delete=models.PROTECT,
        db_column="fmp_pharmacy_software",
        related_name="file_db_mapping_pharmacy_software",
        blank=True,
        null=True,
        to_field="id",
    )

    class Meta:
        db_table = "OPT_FMP_FileDBMapping"


class BinGroups(CoreModel):
    name = models.CharField(db_column="bgp_name", max_length=128)

    class Meta:
        db_table = "OPT_BGP_BinGroups"

    def __str__(self):
        return self.name


class BinNumbers(CoreModel):

    number = models.BigIntegerField(db_column="bnm_number", blank=True, null=True)
    bin_groups = models.ForeignKey(
        BinGroups,
        on_delete=models.PROTECT,
        db_column="bnm_bingroups",
        related_name="binnumber_bingroup",
        blank=True,
        null=True,
        to_field="id",
    )

    class Meta:
        db_table = "OPT_BNM_BinNumbers"


class ErrorLogs(CoreModel):
    process_log = models.ForeignKey(
        ProcessLogHdr,
        on_delete=models.PROTECT,
        db_column="erl_process_log_id",
        related_name="error_log_process_log",
        blank=True,
        null=True,
        to_field="id",
    )
    error_message = models.TextField(
        db_column="erl_error_message", blank=True, null=True
    )
    error_type = models.TextField(
        db_column="erl_error_type", blank=True, null=True, max_length=128
    )
    error_severity = models.ForeignKey(
        ErrorSeverity,
        on_delete=models.PROTECT,
        db_column="erl_error_severity",
        related_name="error_log_error_severity",
        blank=True,
        null=True,
        to_field="id",
    )
    error_location = models.TextField(
        db_column="erl_error_location", blank=True, null=True
    )
    user_context = models.TextField(db_column="erl_user_context", blank=True, null=True)
    error_stack_trace = models.TextField(
        db_column="erl_error_stack_trace", blank=True, null=True
    )

    class Meta:
        db_table = "OPT_ERL_ErrorLogs"
