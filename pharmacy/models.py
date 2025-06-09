from django.db import models
from core.models import CoreModel, CoreLookupModel
from .constants import ProcessingStatusCodes

from person.models import Address
from person.models import Person


class PharmacySoftware(CoreLookupModel):

    class Meta:
        db_table = "CFG_PHS_PHARMACYSOFTWARE"


class Pharmacy(CoreModel):
    corp_name = models.CharField(
        db_column="phm_corp_name", max_length=128, blank=True, null=True
    )
    dba = models.CharField(db_column="phm_dba", max_length=128, blank=True, null=True)
    email = models.CharField(
        db_column="phm_email", max_length=128, blank=True, null=True
    )
    phone = models.BigIntegerField(db_column="phm_phone", blank=True, null=True)
    cell = models.BigIntegerField(db_column="phm_cell", blank=True, null=True)
    fax = models.BigIntegerField(db_column="phm_fax", blank=True, null=True)
    state_license = models.BigIntegerField(
        db_column="phm_state_license", blank=True, null=True
    )
    dea = models.CharField(db_column="phm_dea", max_length=128, blank=True, null=True)
    npi = models.BigIntegerField(db_column="phm_npi", blank=True, null=True)
    ncpa = models.CharField(db_column="phm_ncpa", max_length=128, blank=True, null=True)
    principal_name = models.CharField(
        db_column="phm_principal_name", max_length=128, blank=True, null=True
    )
    principal_cell = models.BigIntegerField(
        db_column="phm_principal_cell", blank=True, null=True
    )
    sap_ship_to_no = models.BigIntegerField(db_column="phm_sap_ship_to_no")
    volume_group_num = models.BigIntegerField(
        db_column="phm_volume_group_num",
        blank=True,
        null=True,
    )
    volume_group = models.ForeignKey(
        "VolumeGroup",
        on_delete=models.PROTECT,
        db_column="phm_volumegroup_id",
        related_name="pharmacy_volumegroup_id",
        blank=True,
        null=True,
        to_field="id",
    )
    campus_master = models.BigIntegerField(db_column="phm_campus_master")
    affiliation_1_name = models.CharField(
        db_column="phm_affiliation_1_name", max_length=128, blank=True, null=True
    )
    contact_name = models.CharField(
        db_column="phm_contact_name", max_length=128, blank=True, null=True
    )
    affiliation_2_name = models.CharField(
        db_column="phm_affiliation_2_name", blank=True, null=True
    )
    gln = models.CharField(db_column="phm_gln", max_length=128, blank=True, null=True)
    principal_email = models.CharField(
        db_column="phm_principal_email", max_length=128, blank=True, null=True
    )
    curr_primary_wholesaler = models.CharField(
        db_column="phm_curr_primary_wholesaler", max_length=128, blank=True, null=True
    )
    curr_total_volume = models.FloatField(
        db_column="phm_curr_total_volume", blank=True, null=True
    )
    est_80_committed_amt = models.FloatField(
        db_column="phm_est_80_committed_amt", blank=True, null=True
    )
    hiv_volume = models.FloatField(db_column="phm_hiv_volume", blank=True, null=True)
    expected_gcr_pct = models.FloatField(
        db_column="phm_expected_gcr_pct", blank=True, null=True
    )
    is_kinray_lead = models.BooleanField(db_column="phm_is_kinray_lead", default=False)
    is_cardinal_lead = models.BooleanField(
        db_column="phm_is_cardinal_lead", default=False
    )
    is_affiliated_member = models.BooleanField(
        db_column="phm_is_affiliated_member", default=False
    )
    is_un_affiliated_member = models.BooleanField(
        db_column="phm_is_un_affiliated_member", default=False
    )
    is_startup_pharma = models.BooleanField(
        db_column="phm_is_startup_pharma", default=False
    )
    is_sub_group_member = models.BooleanField(
        db_column="phm_is_sub_group_member", default=False
    )
    sub_group_name = models.CharField(
        db_column="phm_sub_group_name", max_length=128, blank=True, null=True
    )
    proposed_payment_terms = models.CharField(
        db_column="phm_proposed_payment_terms", blank=True, null=True
    )
    status = models.ForeignKey(
        "PharmacyStatus",
        on_delete=models.PROTECT,
        db_column="phm_status",
        related_name="pharmacy_status_pharmacystatus_id",
        blank=True,
        null=True,
        to_field="id",
    )
    address = models.ForeignKey(
        Address,
        on_delete=models.PROTECT,
        db_column="phm_address",
        related_name="pharmacy_address_address_id",
        blank=True,
        null=True,
        to_field="id",
    )
    sales_contact = models.ForeignKey(
        Person,
        on_delete=models.PROTECT,
        db_column="phm_sales_contact",
        related_name="pharmacy_sales_contact_person_id",
        blank=True,
        null=True,
        to_field="id",
    )
    software = models.ForeignKey(
        PharmacySoftware,
        on_delete=models.PROTECT,
        db_column="phm_pharmacy_software",
        related_name="pharmacy_software",
        to_field="id",
    )

    class Meta:
        db_table = "OPT_PHM_Pharmacy"

    def __str__(self):
        return self.corp_name


class PharmacySalesInfo(CoreModel):
    cust_ship_number = models.BigIntegerField(
        db_column="psi_cust_ship_number", blank=True, null=True
    )
    cust_sold_number = models.BigIntegerField(
        db_column="psi_cust_sold_number", blank=True, null=True
    )
    ship_to_customer_name = models.CharField(
        db_column="psi_ship_to_customer_name", blank=True, null=True
    )
    dba = models.CharField(db_column="psi_dba", max_length=128, blank=True, null=True)
    volume_group_number = models.BigIntegerField(
        db_column="psi_volume_group_number", blank=True, null=True
    )
    volume_group_name = models.CharField(
        db_column="psi_volume_group_name", max_length=128, blank=True, null=True
    )
    campus_number = models.BigIntegerField(
        db_column="psi_campus_number", blank=True, null=True
    )
    reporting_period_start = models.DateField(
        db_column="psi_reporting_period_start", blank=True, null=True
    )
    reporting_period_end = models.DateField(
        db_column="psi_reporting_period_end", blank=True, null=True
    )
    ship_to_default_delivery_plant = models.CharField(
        db_column="psi_ship_to_default_delivery_plant",
        max_length=128,
        blank=True,
        null=True,
    )
    source_compliance_pct_base_member = models.FloatField(
        db_column="psi_source_compliance_pct_base_member", blank=True, null=True
    )
    source_compliance_pct_new_member = models.FloatField(
        db_column="psi_source_compliance_pct_new_member", blank=True, null=True
    )
    total_sales = models.FloatField(db_column="psi_total_sales", blank=True, null=True)
    rx_sales = models.FloatField(db_column="psi_rx_sales", blank=True, null=True)
    brand_rx_sales = models.FloatField(
        db_column="psi_brand_rx_sales", blank=True, null=True
    )
    generic_rx_sales = models.FloatField(
        db_column="psi_generic_rx_sales", blank=True, null=True
    )
    gpo_generic_sales = models.FloatField(
        db_column="psi_gpo_generic_sales", blank=True, null=True
    )
    source_sales = models.FloatField(
        db_column="psi_source_sales", blank=True, null=True
    )
    source_override_sales = models.FloatField(
        db_column="psi_source_override_sales", blank=True, null=True
    )
    net_source_sales = models.FloatField(
        db_column="psi_net_source_sales", blank=True, null=True
    )
    generic_source_sales = models.FloatField(
        db_column="psi_generic_source_sales", blank=True, null=True
    )
    generic_source_overrides = models.FloatField(
        db_column="psi_generic_source_overrides", blank=True, null=True
    )
    net_generic_source_sales = models.FloatField(
        db_column="psi_net_generic_source_sales", blank=True, null=True
    )
    antidiabetic_sales = models.FloatField(
        db_column="psi_antidiabetic_sales", blank=True, null=True
    )
    antidiabeticglp1_sales = models.FloatField(
        db_column="psi_antidiabeticglp1_sales", blank=True, null=True
    )
    antipsychotic_sales = models.FloatField(
        db_column="psi_antipsychotic_sales", blank=True, null=True
    )
    spx_sales = models.FloatField(db_column="psi_spx_sales", blank=True, null=True)
    spx_hiv = models.FloatField(db_column="psi_spx_hiv", blank=True, null=True)
    spx_hep_c = models.FloatField(db_column="psi_spx_hep_c", blank=True, null=True)
    spx_cancer = models.FloatField(db_column="psi_spx_cancer", blank=True, null=True)
    spx_ra = models.FloatField(db_column="psi_spx_ra", blank=True, null=True)
    spx_ms = models.FloatField(db_column="psi_spx_ms", blank=True, null=True)
    spd_sales = models.FloatField(db_column="psi_spd_sales", blank=True, null=True)
    brand_rx_dropship_sales = models.FloatField(
        db_column="psi_brand_rx_dropship_sales", blank=True, null=True
    )
    non_rx_sales = models.FloatField(
        db_column="psi_non_rx_sales", blank=True, null=True
    )
    affiliation_level3_number = models.FloatField(
        db_column="psi_affiliation_level3_number", blank=True, null=True
    )
    affiliation_level3_name = models.CharField(
        db_column="psi_affiliation_level3_name", max_length=128, blank=True, null=True
    )
    original_info = models.JSONField(db_column="psi_original_info")
    pharmacy = models.ForeignKey(
        Pharmacy,
        on_delete=models.PROTECT,
        db_column="psi_pharmacy",
        related_name="pharmacysalesinfo_pharmacy_pharmacy_id",
        blank=True,
        null=True,
        to_field="id",
    )

    class Meta:
        db_table = "OPT_PSI_PharmacySalesInfo"


class VolumeGroupSalesInfo(CoreModel):
    volume_group_number = models.BigIntegerField(db_column="vgi_volume_group_number")
    volume_group_name = models.CharField(
        db_column="vgi_volume_group_name", max_length=128
    )
    reporting_period_start = models.DateField(
        db_column="vgi_reporting_period_start", blank=True, null=True
    )
    reporting_period_end = models.DateField(
        db_column="vgi_reporting_period_end", blank=True, null=True
    )
    number_of_campus_locations = models.BigIntegerField(
        db_column="vgi_number_of_campus_locations", blank=True, null=True
    )
    source_compliance_pct_base_member = models.FloatField(
        db_column="vgi_source_compliance_pct_base_member", blank=True, null=True
    )
    source_compliance_pct_new_member = models.FloatField(
        db_column="vgi_source_compliance_pct_new_member", blank=True, null=True
    )
    total_sales = models.FloatField(db_column="vgi_total_sales", blank=True, null=True)
    rx_sales = models.FloatField(db_column="vgi_rx_sales", blank=True, null=True)
    brand_rx_sales = models.FloatField(
        db_column="vgi_brand_rx_sales", blank=True, null=True
    )
    generic_rx_sales = models.FloatField(
        db_column="vgi_generic_rx_sales", blank=True, null=True
    )
    gpo_generic_sales = models.FloatField(
        db_column="vgi_gpo_generic_sales", blank=True, null=True
    )
    source_sales = models.FloatField(
        db_column="vgi_source_sales", blank=True, null=True
    )
    source_override_sales = models.FloatField(
        db_column="vgi_source_override_sales", blank=True, null=True
    )
    net_source_sales = models.FloatField(
        db_column="vgi_net_source_sales", blank=True, null=True
    )
    generic_source_sales = models.FloatField(
        db_column="vgi_generic_source_sales", blank=True, null=True
    )
    generic_source_overrides = models.FloatField(
        db_column="vgi_generic_source_overrides", blank=True, null=True
    )
    net_generic_source_sales = models.FloatField(
        db_column="vgi_net_generic_source_sales", blank=True, null=True
    )
    antidiabetic_sales = models.FloatField(
        db_column="vgi_antidiabetic_sales", blank=True, null=True
    )
    antidiabeticglp1_sales = models.FloatField(
        db_column="vgi_antidiabeticglp1_sales", blank=True, null=True
    )
    antipsychotic_sales = models.FloatField(
        db_column="vgi_antipsychotic_sales", blank=True, null=True
    )
    spx_sales = models.FloatField(db_column="vgi_spx_sales", blank=True, null=True)
    spx_hiv = models.FloatField(db_column="vgi_spx_hiv", blank=True, null=True)
    spx_hep_c = models.FloatField(db_column="vgi_spx_hep_c", blank=True, null=True)
    spx_cancer = models.FloatField(db_column="vgi_spx_cancer", blank=True, null=True)
    spx_ra = models.FloatField(db_column="vgi_spx_ra", blank=True, null=True)
    spx_ms = models.FloatField(db_column="vgi_spx_ms", blank=True, null=True)
    spd_sales = models.FloatField(db_column="vgi_spd_sales", blank=True, null=True)
    brand_rx_dropship_sales = models.FloatField(
        db_column="vgi_brand_rx_dropship_sales", blank=True, null=True
    )
    non_rx_sales = models.FloatField(
        db_column="vgi_non_rx_sales", blank=True, null=True
    )
    original_info = models.JSONField(db_column="vgi_original_info")
    volumegroup = models.ForeignKey(
        "VolumeGroup",
        on_delete=models.PROTECT,
        db_column="vgi_volumegroup",
        related_name="volumegroupsalesinfo_volumegroup_volumegroup_id",
        blank=True,
        null=True,
        to_field="id",
    )

    class Meta:
        db_table = "OPT_VGI_VolumeGroupSalesInfo"


class GroupSalesInfo(CoreModel):
    group_name = models.CharField(db_column="gsi_group_name", max_length=128)
    reporting_period_start = models.DateField(
        db_column="gsi_reporting_period_start", blank=True, null=True
    )
    reporting_period_end = models.DateField(
        db_column="gsi_reporting_period_end", blank=True, null=True
    )
    source_compliance_pct_base_member = models.FloatField(
        db_column="gsi_source_compliance_pct_base_member", blank=True, null=True
    )
    source_compliance_pct_new_member = models.FloatField(
        db_column="gsi_source_compliance_pct_new_member", blank=True, null=True
    )
    total_sales = models.FloatField(db_column="gsi_total_sales", blank=True, null=True)
    rx_sales = models.FloatField(db_column="gsi_rx_sales", blank=True, null=True)
    brand_rx_sales = models.FloatField(
        db_column="gsi_brand_rx_sales", blank=True, null=True
    )
    generic_rx_sales = models.FloatField(
        db_column="gsi_generic_rx_sales", blank=True, null=True
    )
    gpo_generic_sales = models.FloatField(
        db_column="gsi_gpo_generic_sales", blank=True, null=True
    )
    source_sales = models.FloatField(
        db_column="gsi_source_sales", blank=True, null=True
    )
    source_override_sales = models.FloatField(
        db_column="gsi_source_override_sales", blank=True, null=True
    )
    net_source_sales = models.FloatField(
        db_column="gsi_net_source_sales", blank=True, null=True
    )
    generic_source_sales = models.FloatField(
        db_column="gsi_generic_source_sales", blank=True, null=True
    )
    generic_source_overrides = models.FloatField(
        db_column="gsi_generic_source_overrides", blank=True, null=True
    )
    net_generic_source_sales = models.FloatField(
        db_column="gsi_net_generic_source_sales", blank=True, null=True
    )
    antidiabetic_sales = models.FloatField(
        db_column="gsi_antidiabetic_sales", blank=True, null=True
    )
    antidiabeticglp1_sales = models.FloatField(
        db_column="gsi_antidiabeticglp1_sales", blank=True, null=True
    )
    antipsychotic_sales = models.FloatField(
        db_column="gsi_antipsychotic_sales", blank=True, null=True
    )
    spx_sales = models.FloatField(db_column="gsi_spx_sales", blank=True, null=True)
    spx_hiv = models.FloatField(db_column="gsi_spx_hiv", blank=True, null=True)
    spx_hep_c = models.FloatField(db_column="gsi_spx_hep_c", blank=True, null=True)
    spx_cancer = models.FloatField(db_column="gsi_spx_cancer", blank=True, null=True)
    spx_ra = models.FloatField(db_column="gsi_spx_ra", blank=True, null=True)
    spx_ms = models.FloatField(db_column="gsi_spx_ms", blank=True, null=True)
    spd_sales = models.FloatField(db_column="gsi_spd_sales", blank=True, null=True)
    brand_rx_dropship_sales = models.FloatField(
        db_column="gsi_brand_rx_dropship_sales", blank=True, null=True
    )
    non_rx_sales = models.FloatField(
        db_column="gsi_non_rx_sales", blank=True, null=True
    )
    original_info = models.JSONField(db_column="gsi_original_info")
    group = models.ForeignKey(
        "Group",
        on_delete=models.PROTECT,
        db_column="gsi_group",
        related_name="groupsalesinfo_group_group_id",
        blank=True,
        null=True,
        to_field="id",
    )

    class Meta:
        db_table = "OPT_GSI_GroupSalesInfo"


class VolumeGroup(CoreModel):
    number = models.BigIntegerField(db_column="vol_number")
    name = models.CharField(db_column="vol_name", max_length=128)
    location_count = models.IntegerField(db_column="vol_location_count", default=0)
    group = models.ForeignKey(
        "Group",
        on_delete=models.PROTECT,
        db_column="gsi_group",
        related_name="volumegroup_group_group_id",
        blank=True,
        null=True,
        to_field="id",
    )

    class Meta:
        db_table = "OPT_VOL_VolumeGroup"


class Group(CoreModel):
    name = models.CharField(db_column="grp_name", max_length=128)

    class Meta:
        db_table = "OPT_GRP_Group"


class PharmacyStatus(CoreLookupModel):
    class Meta:
        db_table = "LKP_PHS_PharmacyStatus"


class RebateInfo(CoreModel):
    div = models.IntegerField(db_column="rbi_div", blank=True, null=True)
    sales_rep_name = models.CharField(
        db_column="rbi_sales_rep_name", max_length=128, blank=True, null=True
    )
    affiliation_level_2 = models.BigIntegerField(
        db_column="rbi_affiliation_level_2", blank=True, null=True
    )
    affiliation_level_2_name = models.CharField(
        db_column="rbi_affiliation_level_2_name", max_length=128, blank=True, null=True
    )
    customer_num = models.BigIntegerField(
        db_column="rbi_customer_num", blank=True, null=True
    )
    customer_name = models.CharField(
        db_column="rbi_customer_name", max_length=128, blank=True, null=True
    )
    dba_name = models.CharField(
        db_column="rbi_dba_name", max_length=128, blank=True, null=True
    )
    volume_group = models.BigIntegerField(
        db_column="rbi_volume_group", blank=True, null=True
    )
    payer_customer_number = models.BigIntegerField(
        db_column="rbi_payer_customer_number", blank=True, null=True
    )
    campus_number = models.BigIntegerField(
        db_column="rbi_campus_number", blank=True, null=True
    )
    net_sales = models.FloatField(db_column="rbi_net_sales", blank=True, null=True)
    total_rx = models.FloatField(db_column="rbi_total_rx", blank=True, null=True)
    brand_net = models.FloatField(db_column="rbi_brand_net", blank=True, null=True)
    source_sales = models.FloatField(
        db_column="rbi_source_sales", blank=True, null=True
    )
    spx_1_net = models.FloatField(db_column="rbi_spx_1_net", blank=True, null=True)
    spx_2_net = models.FloatField(db_column="rbi_spx_2_net", blank=True, null=True)
    spx_3_net = models.FloatField(db_column="rbi_spx_3_net", blank=True, null=True)
    spx_4_net = models.FloatField(db_column="rbi_spx_4_net", blank=True, null=True)
    spx_5_net = models.FloatField(db_column="rbi_spx_5_net", blank=True, null=True)
    glp_1_anti_diabetics = models.FloatField(
        db_column="rbi_glp-1_anti-diabetics", blank=True, null=True
    )  # Field renamed to remove unsuitable characters.
    spd_sales = models.FloatField(db_column="rbi_spd_sales", blank=True, null=True)
    dropship = models.FloatField(db_column="rbi_dropship", blank=True, null=True)
    brand_rebatable = models.FloatField(
        db_column="rbi_brand_rebatable", blank=True, null=True
    )
    net_rx_after_exclusions = models.FloatField(
        db_column="rbi_net_rx_after_exclusions", blank=True, null=True
    )
    source_rebatable = models.FloatField(
        db_column="rbi_source_rebatable", blank=True, null=True
    )
    campus_source_sales = models.FloatField(
        db_column="rbi_campus_source_sales", blank=True, null=True
    )
    campus_net_rx_after_exclusions = models.FloatField(
        db_column="rbi_campus_net_rx_after_exclusions", blank=True, null=True
    )
    generic_compliance = models.FloatField(
        db_column="rbi_generic_compliance", blank=True, null=True
    )
    campus_compliance_based_on_net_rx_sales_after_exclusions = models.FloatField(
        db_column="rbi_campus_compliance_based_on_net_rx_sales_after_exclusions",
        blank=True,
        null=True,
    )
    volume_group_compliance_based_on_net_rx_sales_after_exclusions = models.FloatField(
        db_column="rbi_volume_group_compliance_based_on_net_rx_sales_after_exclusions",
        blank=True,
        null=True,
    )
    net_sales_per_location = models.FloatField(
        db_column="rbi_net_sales_per_location", blank=True, null=True
    )
    revised_payment_terms = models.FloatField(
        db_column="rbi_revised_payment_terms", blank=True, null=True
    )
    payment_terms_rebate_pct = models.FloatField(
        db_column="rbi_payment_terms_rebate_pct", blank=True, null=True
    )
    payments_terms_rebate_amt = models.FloatField(
        db_column="rbi_payments_terms_rebate_amt", blank=True, null=True
    )
    monthly_source_rebate_pct_via_campus_compliance = models.FloatField(
        db_column="rbi_monthly_source_rebate_pct_via_campus_compliance",
        blank=True,
        null=True,
    )
    monthly_source = models.FloatField(
        db_column="rbi_monthly_source", blank=True, null=True
    )
    brand_rebate_pct = models.FloatField(
        db_column="rbi_brand_rebate_pct", blank=True, null=True
    )
    brand_rebate_amt = models.FloatField(
        db_column="rbi_brand_rebate_amt", blank=True, null=True
    )
    total_brand_rebate_pct = models.FloatField(
        db_column="rbi_total_brand_rebate_pct", blank=True, null=True
    )
    total_brand = models.FloatField(db_column="rbi_total_brand", blank=True, null=True)
    monthly_source_admin_fee_pct = models.FloatField(
        db_column="rbi_monthly_source_admin_fee_pct", blank=True, null=True
    )
    monthly_source_admin_fee_amt = models.FloatField(
        db_column="rbi_monthly_source_admin_fee_amt", blank=True, null=True
    )
    original_info = models.JSONField(db_column="rbi_original_info")
    pharmacy = models.ForeignKey(
        Pharmacy,
        on_delete=models.PROTECT,
        db_column="rbi_pharmacy",
        related_name="rebateinfo_pharmacy_pharmacy_id",
        blank=True,
        null=True,
        to_field="id",
    )

    class Meta:
        db_table = "OPT_RBI_RebateInfo"


class ProcessingStatus(CoreLookupModel):
    class Meta:
        db_table = "OPT_PST_ProcessingStatus"


class FileProcessingLogs(CoreModel):
    file_name = models.CharField(
        db_column="fpl_file_name", max_length=128, blank=True, null=True
    )
    status = models.ForeignKey(
        ProcessingStatus,
        on_delete=models.PROTECT,
        related_name="+",
        db_column="fpl_status",
        to_field="id",
        blank=True,
        null=True,
    )
    log = models.TextField(db_column="tat_log", blank=True, null=True)
    file_location = models.CharField(
        db_column="fpl_file_location", max_length=128, blank=True, null=True
    )

    class Meta:
        db_table = "OPT_FPL_FileProcessingLogs"
