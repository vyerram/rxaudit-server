from enum import Enum

from audit.models import ProcessLogHdr


class FileTypes(Enum):
    Pharmacy = "pmc"
    Distributor = "dtb"
    ComparedResult = "comp"


class FileFormats(Enum):
    CSV = ".csv"
    XLS = ".xls"
    XLSX = ".xlsx"


class ErrorSeverities(Enum):
    Error = "ER"
    Info = "IN"
    Warning = "WA"
    Critical = "CR"


class DateFormats:
    formats = [
        {"label": "mm/dd/yyyy", "value": "%m/%d/%Y"},
        {"label": "mm-dd-yyyy", "value": "%m-%d-%Y"},
        {"label": "mmddyyyy", "value": "%m%d%Y"},
        {"label": "mm/dd/yy", "value": "%m/%d/%y"},
        {"label": "mm-dd-yy", "value": "%m-%d-%y"},
        {"label": "mmddyy", "value": "%m%d%y"},
        {"label": "yyyy/mm/dd", "value": "%Y/%m/%d"},
        {"label": "yyyy-mm-dd", "value": "%Y-%m-%d"},
        {"label": "yyyymmdd", "value": "%Y%m%d"},
        {"label": "yy/mm/dd", "value": "%y/%m/%d"},
        {"label": "yy-mm-dd", "value": "%y-%m-%d"},
        {"label": "yymmdd", "value": "%y%m%d"},
        {"label": "dd-mm-yyyy", "value": "%d-%m-%Y"},
        {"label": "dd-mm-yy", "value": "%d-%m-%y"},
        {"label": "dd/mm/yyyy", "value": "%d/%m/%Y"},
        {"label": "dd/mm/yy", "value": "%d/%m/%y"},
    ]


def get_output_report_sql(
    process_log_id,
    pharmacy_from_date,
    pharmacy_to_date,
    distributor_from_date,
    distributor_to_date,
    group,
    pcn,
    bin_number,
):
    pharmacy_date_filter = (
        f"AND (pad_date BETWEEN '{pharmacy_from_date}' AND '{pharmacy_to_date}' OR pad_date = '1900-01-01')"
        if pharmacy_from_date and pharmacy_to_date
        else ""
    )
    distributor_date_filter = (
        f"AND (dad_date BETWEEN '{distributor_from_date}' AND '{distributor_to_date}' OR dad_date = '1900-01-01')"
        if distributor_from_date and distributor_to_date
        else ""
    )
    group_filter = f"AND pad_group = '{group}'" if group else ""
    pcn_filter = f"AND pad_pcn = '{pcn}'" if pcn else ""
    bin_filter = f"AND pad_ins_bin_number = '{bin_number}'" if bin_number else ""

    process_log = ProcessLogHdr.objects.filter(id=process_log_id).prefetch_related(
        "payment_method", "claim_status"
    )
    selected_payment_methods = [pm.code for pm in process_log[0].payment_method.all()]
    if selected_payment_methods:
        payment_option_filter = ""
        if "CA" in selected_payment_methods and "IN" not in selected_payment_methods:
            payment_option_filter = "AND pad_payment_option = 'C'"
        elif "IN" in selected_payment_methods:
            payment_option_filter = "AND pad_payment_option != 'C'"
    else:
        payment_option_filter = ""

    claim_status_codes = [cs.code for cs in process_log[0].claim_status.all()]
    if claim_status_codes:
        claim_status_filter = f" AND pad_claim_status IN ({','.join(repr(code) for code in claim_status_codes)})"
    else:
        claim_status_filter = ""
    output_report_statement = f"""SELECT 
        COALESCE(pharmacy_data."NDC", distributor_data.dad_ndc) AS "NDC",
        MAX(pharmacy_data."Brand") AS "Brand",
        MAX(pharmacy_data."Strength") AS "Strength",
        MAX(pharmacy_data."Pack") AS "Pack",
        COALESCE(MAX(pharmacy_data."Drug Name"), MAX(distributor_data.dad_drug_name)) AS "Drug Name",
        SUM(pharmacy_data."Dispense Qty in Packs") AS "Dispense Qty in Packs",
        SUM(pharmacy_data."Dispense Qty in Units") AS "Dispense Qty in Units",
        SUM(pharmacy_data."Total Insurance paid") AS "Total Insurance paid",
        SUM(pharmacy_data."Patient Co-pay") AS "Patient Co-pay",
        SUM(pharmacy_data."No of RX") AS "No of RX",
        distributor_data.description AS description,
        SUM(distributor_data.distributor_quantity) AS distributor_quantity
    FROM
        (SELECT
            pad_ndc AS "NDC",
            pad_brand AS "Brand",
            pad_strength AS "Strength",
            pad_size AS "Pack",
            pad_drug_name AS "Drug Name",
            (SUM(pad_quantity) / COALESCE(NULLIF(CAST(pad_size AS DECIMAL), 0), 1))  "Dispense Qty in Packs",
            sum(pad_quantity) as "Dispense Qty in Units",
            SUM(pad_ins_paid) AS "Total Insurance paid",
            SUM(pad_patient_copay) AS "Patient Co-pay",
            COUNT(pad_ndc) AS "No of RX"
        FROM
            public."OPT_PAD_PharmacyAuditData"
        WHERE
            pad_process_log_id = '{process_log_id}'
            {pharmacy_date_filter}
            {payment_option_filter}
            {claim_status_filter}
            {group_filter}
            {pcn_filter}
            {bin_filter}
        GROUP BY
            pad_ndc, pad_brand, pad_strength, pad_drug_name, pad_size
        ) AS pharmacy_data
    FULL OUTER JOIN
        (SELECT
            dad_ndc,
            description,
            dad_drug_name,
            SUM(dad_quantity) AS distributor_quantity
        FROM
            "OPT_DAD_DistributorAuditData"
        JOIN
            "OPT_DTB_Distributors"
        ON
            "OPT_DTB_Distributors".id = dad_distributor
        WHERE
            dad_process_log_id = '{process_log_id}'
            {distributor_date_filter}
        GROUP BY
            dad_ndc, description, dad_drug_name
        ) AS distributor_data
    ON
        pharmacy_data."NDC" = distributor_data.dad_ndc
    GROUP BY
        COALESCE(pharmacy_data."NDC", distributor_data.dad_ndc),
        distributor_data.description
"""

    return output_report_statement


def get_output_bins_sql(
    process_log_id,
    pharmacy_from_date,
    pharmacy_to_date,
    distributor_from_date,
    distributor_to_date,
    group,
    pcn,
    bin_number,
):
    pharmacy_date_filter = (
        f"AND (pad_date BETWEEN '{pharmacy_from_date}' AND '{pharmacy_to_date}' OR pad_date = '1900-01-01')"
        if pharmacy_from_date and pharmacy_to_date
        else ""
    )
    distributor_date_filter = (
        f"AND (dad_date BETWEEN '{distributor_from_date}' AND '{distributor_to_date}' OR dad_date = '1900-01-01')"
        if distributor_from_date and distributor_to_date
        else ""
    )
    group_filter = f"AND pad_group = '{group}'" if group else ""
    pcn_filter = f"AND pad_pcn = '{pcn}'" if pcn else ""
    bin_filter = f"AND pad_ins_bin_number = '{bin_number}'" if bin_number else ""
    process_log = ProcessLogHdr.objects.filter(id=process_log_id).prefetch_related(
        "payment_method", "claim_status"
    )
    selected_payment_methods = [pm.code for pm in process_log[0].payment_method.all()]
    if selected_payment_methods:
        payment_option_filter = ""
        if "CA" in selected_payment_methods and "IN" not in selected_payment_methods:
            payment_option_filter = "AND pad_payment_option = 'C'"
        elif "IN" in selected_payment_methods:
            payment_option_filter = "AND pad_payment_option != 'C'"
    else:
        payment_option_filter = ""

    claim_status_codes = [cs.code for cs in process_log[0].claim_status.all()]
    if claim_status_codes:
        claim_status_filter = f" AND pad_claim_status IN ({','.join(repr(code) for code in claim_status_codes)})"
    else:
        claim_status_filter = ""

    output_report_statement = f"""SELECT * FROM (select pad_ndc as "NDC",pad_brand as "Brand",pad_strength as "Strength",pad_size as "Pack",pad_drug_name as "Drug Name", (sum(pad_quantity)/COALESCE(NULLIF(cast(pad_size as decimal), 0), 1)) as "Dispense Qty in Packs", sum(pad_quantity) as "Dispense Qty in Units",
                                    sum(pad_ins_paid) as "Total Insurance paid", sum(pad_patient_copay) as "Patient Co-pay", count(pad_ndc) as "No of RX", bgp_name from public."OPT_PAD_PharmacyAuditData"
                                    join "OPT_BNM_BinNumbers" on pad_ins_bin_number = bnm_number join "OPT_BGP_BinGroups" on bnm_bingroups = "OPT_BGP_BinGroups".id
                                    where pad_process_log_id = '{process_log_id}' {pharmacy_date_filter}  {payment_option_filter} {claim_status_filter} {group_filter} {pcn_filter} {bin_filter} group by pad_ndc,pad_brand,pad_strength,pad_drug_name,pad_size, bgp_name) AS pharmacy_data
                                    left outer join (select dad_ndc,description, sum(dad_quantity) as distributor_quantity from "OPT_DAD_DistributorAuditData" join "OPT_DTB_Distributors" on "OPT_DTB_Distributors".id = dad_distributor where dad_process_log_id = '{process_log_id}' {distributor_date_filter} group by dad_ndc, description) AS distributor_data
                                    on pharmacy_data."NDC" = distributor_data.dad_ndc
                                    union
                                    SELECT * FROM (select pad_ndc as "NDC",pad_brand as "Brand",pad_strength as "Strength",pad_size as "Pack",pad_drug_name as "Drug Name", (sum(pad_quantity)/COALESCE(NULLIF(cast(pad_size as decimal), 0), 1)) as "Dispense Qty in Packs", sum(pad_quantity) as "Dispense Qty in Units",
                                    sum(pad_ins_paid) as "Total Insurance paid", sum(pad_patient_copay) as "Patient Co-pay", count(pad_ndc) as "No of RX", 'Miscellaneous Bins' as bgp_name from public."OPT_PAD_PharmacyAuditData"
                                    left join "OPT_BNM_BinNumbers" on pad_ins_bin_number = bnm_number
                                    where pad_process_log_id = '{process_log_id}' {pharmacy_date_filter}  {payment_option_filter} {claim_status_filter} {group_filter} {pcn_filter} {bin_filter}
                                    and pad_ins_bin_number not in (select pad_ins_bin_number from "OPT_PAD_PharmacyAuditData"
                                    LEFT JOIN "OPT_BNM_BinNumbers" ON pad_ins_bin_number = bnm_number
                                    join "OPT_BGP_BinGroups" on bnm_bingroups = "OPT_BGP_BinGroups".id
                                    where  pad_process_log_id = '{process_log_id}' {pharmacy_date_filter}  {payment_option_filter} {claim_status_filter} {group_filter} {pcn_filter} {bin_filter} )
                                    group by pad_ndc,pad_brand,pad_strength,pad_drug_name,pad_size) AS pharmacy_data
                                    left outer join (select dad_ndc,description, sum(dad_quantity) as distributor_quantity from "OPT_DAD_DistributorAuditData" join "OPT_DTB_Distributors" on "OPT_DTB_Distributors".id = dad_distributor where dad_process_log_id = '{process_log_id}' {distributor_date_filter} group by dad_ndc, description) AS distributor_data
                                    on pharmacy_data."NDC" = distributor_data.dad_ndc"""
    return output_report_statement


def get_bin_raw_sql(
    process_log_id, pharmacy_from_date, pharmacy_to_date, group, pcn, bin_number
):
    pharmacy_date_filter = (
        f"AND (pad_date BETWEEN '{pharmacy_from_date}' AND '{pharmacy_to_date}' OR pad_date = '1900-01-01')"
        if pharmacy_from_date and pharmacy_to_date
        else ""
    )
    group_filter = f"AND pad_group = '{group}'" if group else ""
    pcn_filter = f"AND pad_pcn = '{pcn}'" if pcn else ""
    bin_filter = f"AND pad_ins_bin_number = '{bin_number}'" if bin_number else ""
    process_log = ProcessLogHdr.objects.filter(id=process_log_id).prefetch_related(
        "payment_method", "claim_status"
    )
    selected_payment_methods = [pm.code for pm in process_log[0].payment_method.all()]
    if selected_payment_methods:
        payment_option_filter = ""
        if "CA" in selected_payment_methods and "IN" not in selected_payment_methods:
            payment_option_filter = "AND pad_payment_option = 'C'"
        elif "IN" in selected_payment_methods:
            payment_option_filter = "AND pad_payment_option != 'C'"
    else:
        payment_option_filter = ""

    claim_status_codes = [cs.code for cs in process_log[0].claim_status.all()]
    if claim_status_codes:
        claim_status_filter = f" AND pad_claim_status IN ({','.join(repr(code) for code in claim_status_codes)})"
    else:
        claim_status_filter = ""

    bin_group_raw_data = f"""
    SELECT pad_ndc as "NDC",
        pad_brand as "Brand",
        pad_strength as "Strength",
        pad_size as "Pack",
        pad_drug_name as "Drug Name",
        pad_quantity as "Dispense Qty in Units",
        pad_ins_paid as "Total Insurance paid",
        pad_patient_copay as "Patient Co-pay",
        pad_ins_bin_number as "Bin Number",
        bgp_name 
    FROM public."OPT_PAD_PharmacyAuditData"
    JOIN "OPT_BNM_BinNumbers" 
    ON pad_ins_bin_number = bnm_number
    JOIN "OPT_BGP_BinGroups" 
    ON bnm_bingroups = "OPT_BGP_BinGroups".id 
    WHERE pad_process_log_id = '{process_log_id}' {pharmacy_date_filter}  {payment_option_filter} {claim_status_filter} {group_filter} {pcn_filter} {bin_filter}

    UNION All

    SELECT pad_ndc as "NDC",
        pad_brand as "Brand",
        pad_strength as "Strength",
        pad_size as "Pack",
        pad_drug_name as "Drug Name",
        pad_quantity as "Dispense Qty in Units",
        pad_ins_paid as "Total Insurance paid",
        pad_patient_copay as "Patient Co-pay",
        pad_ins_bin_number as "Bin Number",
        'Miscellaneous Bins' as bgp_name
    FROM public."OPT_PAD_PharmacyAuditData"
    LEFT JOIN "OPT_BNM_BinNumbers" 
    ON pad_ins_bin_number = bnm_number
    WHERE pad_process_log_id = '{process_log_id}' {pharmacy_date_filter}  {payment_option_filter} {claim_status_filter} {group_filter} {pcn_filter} {bin_filter}
    AND pad_ins_bin_number NOT IN (
        SELECT pad_ins_bin_number 
        FROM "OPT_PAD_PharmacyAuditData" 
        LEFT JOIN "OPT_BNM_BinNumbers" 
        ON pad_ins_bin_number = bnm_number
        JOIN "OPT_BGP_BinGroups" 
        ON bnm_bingroups = "OPT_BGP_BinGroups".id 
        WHERE pad_process_log_id = '{process_log_id}' {pharmacy_date_filter}  {payment_option_filter} {claim_status_filter} {group_filter} {pcn_filter} {bin_filter})
    """

    return bin_group_raw_data
