from django.core.mail import EmailMessage
import pandas as pd

from django.core.management.base import BaseCommand, CommandError
from django.apps import apps
from core.migrations.utilities.util import migrate_bulk_data
from core.utils import upload_file
from correspondence.models import Template
from correspondence.views import generate_document_for_template
from pharmacy.constants import ProcessingStatusCodes
from pharmacy.models import Pharmacy
from pharmacy import models, serializers
import os
from django.conf import settings
import json
from datetime import datetime
from urllib.request import urlretrieve
from django.core.mail import send_mail
from pharmacy.utils import (
    ProcessAllwinDailyFile,
    ProcessRebateData,
    get_processing_status,
)


class Command(BaseCommand):
    help = "To test code quickly"
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument(
            "--excel",
            type=str,
            help="Input of excel from which code needs to be generated.",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.generic_column_mapping = {
            "Source Compliance % Base Member": "source_compliance_pct_base_member",
            "Source Compliance % New Member": "source_compliance_pct_new_member",
            "Total Sales": "total_sales",
            "Rx Sales": "rx_sales",
            "Brand Rx Sales": "brand_rx_sales",
            "Generic Rx Sales": "generic_rx_sales",
            "GPO Generic Sales": "gpo_generic_sales",
            "Source Sales": "source_sales",
            "Source Override Sales": "source_override_sales",
            "Net Source Sales": "net_source_sales",
            "Generic Source Sales": "generic_source_sales",
            "Generic Source Overrides": "generic_source_overrides",
            "Net Generic Source Sales": "net_generic_source_sales",
            "Antidiabetic Sales": "antidiabetic_sales",
            "Antidiabetic GLP-1 Sales": "antidiabeticglp1_sales",
            "Antipsychotic Sales": "antipsychotic_sales",
            "SPX Sales": "spx_sales",
            "SPX HIV": "spx_hiv",
            "SPX Hep C": "spx_hep_c",
            "SPX Cancer": "spx_cancer",
            "SPX RA": "spx_ra",
            "SPX MS": "spx_ms",
            "SPD Sales": "spd_sales",
            "Brand Rx Dropship Sales": "brand_rx_dropship_sales",
            "Non RX Sales": "non_rx_sales",
        }

    def handle(self, **options):
        try:
            from os import listdir
            from os.path import isfile, join

            get_data_path = (
                "C:\\Users\\aspyr_1\\OneDrive\\Desktop\\Files Supplied\\Get_data"
            )
            onlyfiles = [
                f for f in listdir(get_data_path) if isfile(join(get_data_path, f))
            ]
            for file in onlyfiles:
                subject = "ALL-WIN- Kinray_Source Comp 2 Calc Report_Daily"
                # file_url = data.get("attachment_link")
                file_name = file
                full_file_name = os.path.join(get_data_path, file_name)
                file_process_logs = models.FileProcessingLogs(
                    file_name=file_name,
                    status=get_processing_status(
                        ProcessingStatusCodes.Inprogress.value
                    ),
                )
                try:
                    if subject not in [
                        "ALL-WIN- Kinray_Source Comp 2 Calc Report_Daily"
                    ]:
                        return
                    upload_file(full_file_name)
                    file_process_logs.file_location = (
                        f"{settings.AWS_BUCKET}/{file_name}"
                    )
                    file_process_logs.save()
                    xls = pd.ExcelFile(full_file_name)
                    if xls.io.__contains__("ALL-WIN- Kinray"):
                        process_allwin_daily_file = ProcessAllwinDailyFile()
                        process_allwin_daily_file.process_daily_report(xls)
                    elif xls.io.__contains__("Rebates"):
                        process_rebate_data_file = ProcessRebateData()
                        process_rebate_data_file.process_rebates_report(xls)
                    xls.close()
                    os.remove(full_file_name)
                    file_process_logs.status = get_processing_status(
                        ProcessingStatusCodes.Success.value
                    )
                    file_process_logs.save(update_fields=["status"])
                    print("Success")
                except Exception as e:
                    nl = "\n"
                    file_process_logs.status = get_processing_status(
                        ProcessingStatusCodes.Failure.value
                    )
                    file_process_logs.save(update_fields=["status"])
                    subject = f"{file_name} processing failed"
                    message = f"""Hi,{nl}{nl}{nl}Please review file {file_name} as it's processing failed due to error {str(e)}.{nl}{nl}{nl}Thanks,{nl}AllwinRx."""
                    email_from = settings.EMAIL_HOST_USER
                    file_processing_recipient_list = (
                        settings.EMAIL_FAILURE_NOTIFICATION_LIST
                    )
                    send_mail(
                        subject, message, email_from, file_processing_recipient_list
                    )
                    print("Failure")
        except Exception as e:
            raise CommandError(e)

    def save_rebate_info(self, sheet_name):
        rebate_columns = {
            "Affiliation Level 2": "affiliation_level_2",
            "Affiliation Level 2 Name": "affiliation_level_2_name",
            "Customer #": "customer_num",
            "Customer Name": "customer_name",
            "DBA Name": "dba_name",
            "Volume Group": "volume_group",
            "Payer Customer Number": "payer_customer_number",
            "Campus Number": "campus_number",
            "Net Sales": "net_sales",
            "Total Rx": "total_rx",
            "Brand Net": "brand_net",
            "Source Sales": "source_sales",
            "SPX 1 Net": "spx_1_net",
            "SPX 2 Net": "spx_2_net",
            "SPX 3 Net": "spx_3_net",
            "SPX 4 Net": "spx_4_net",
            "SPX 5 Net": "spx_5_net",
            "GLP-1 Anti-Diabetics": "glp_1_anti_diabetics",
            "SPD Sales": "spd_sales",
            "Dropship": "dropship",
            "Brand Rebatable": "brand_rebatable",
            "Net RX After exclusions": "net_rx_after_exclusions",
            "Source Rebatable": "source_rebatable",
            "Campus Source Sales": "campus_source_sales",
            "Campus \nNet RX After exclusions": "campus_net_rx_after_exclusions",
            "Generic Compliance": "generic_compliance",
            "Campus Compliance based on Net RX Sales (after exclusions)": "campus_compliance_based_on_net_rx_sales_after_exclusions",
            "Volume Group Compliance based on Net RX Sales (after exclusions)": "volume_group_compliance_based_on_net_rx_sales_after_exclusions",
            "Net Sales per Location": "net_sales_per_location",
            "Revised Payment Terms": "revised_payment_terms",
            "Payment Terms Rebate %": "payment_terms_rebate_pct",
            "Payments Terms Rebate $": "payments_terms_rebate_amt",
            "Monthly Source Rebate % - via Campus Compliance": "monthly_source_rebate_pct_via_campus_compliance",
            "Monthly Source": "monthly_source",
            "Brand Rebate %": "brand_rebate_pct",
            "Brand Rebate $": "brand_rebate_amt",
            "Total Brand Rebate %": "total_brand_rebate_pct",
            "Total Brand": "total_brand",
        }
        rebate_summary = self.read_xl_sheet(sheet_name)

        rebate_summary["original_info"] = rebate_summary.apply(
            self.get_original_info, axis=1
        )

        rebate_summary = rebate_summary.rename(columns=rebate_columns)
        rebate_summary_rec = rebate_summary.to_dict("records")
        migrate_bulk_data(apps, "pharmacy", "RebateInfo", rebate_summary_rec)

    def save_group_summary(self, sheet_name):
        summary = {}
        group_summary = self.read_xl_sheet(sheet_name)
        summary["original_info"] = json.loads(group_summary.to_json(orient="records"))
        group_summary.columns = ["group_key", "group_val", ""]
        for index, summary_rec in group_summary.iterrows():
            if summary_rec["group_key"] == "Level 1 Group":
                summary["group_name"] = summary_rec["group_val"]
                summary["group__name"] = summary_rec["group_val"]
            elif summary_rec["group_key"] == "Reporting Period":
                reporting_period_start, reporting_period_end = map(
                    str.strip, summary_rec["group_val"].split("-")
                )
                summary["reporting_period_start"] = datetime.strptime(
                    reporting_period_start, "%m/%d/%y"
                ).strftime("%Y-%m-%d")
                summary["reporting_period_end"] = datetime.strptime(
                    reporting_period_end, "%m/%d/%y"
                ).strftime("%Y-%m-%d")
            elif summary_rec["group_key"] in self.generic_column_mapping.keys():
                summary[self.generic_column_mapping[summary_rec["group_key"]]] = (
                    summary_rec["group_val"]
                )

        migrate_bulk_data(apps, "pharmacy", "GroupSalesInfo", [summary])
        return summary

    def save_account_mtd(self, sheet_name):
        mtd_column_mapping = {
            "Affiliation Level 3 Number": "affiliation_level3_number",
            "Affiliation Level 3 Name": "affiliation_level3_name",
            "Ship To Customer Number": "cust_ship_number",
            "Sold To Customer Number": "cust_sold_number",
            "Ship To Customer Name": "ship_to_customer_name",
            "DBA": "dba",
            "Volume Group Number": "volume_group_number",
            "Volume Group  Name": "volume_group_name",
            "Campus Number": "campus_number",
            "Ship To Default Delivery Plant": "ship_to_default_delivery_plant",
        }
        mtd_column_mapping.update(self.generic_column_mapping)
        pharmacy_account_mtd = self.read_xl_sheet(sheet_name)
        pharmacy_account_mtd["original_info"] = pharmacy_account_mtd.apply(
            self.get_original_info, axis=1
        )
        pharmacy_account_mtd = pharmacy_account_mtd.rename(columns=mtd_column_mapping)
        pharmacy_account_mtd_rec = pharmacy_account_mtd.to_dict("records")
        migrate_bulk_data(
            apps, "pharmacy", "PharmacySalesInfo", pharmacy_account_mtd_rec
        )
        return pharmacy_account_mtd

    def save_volume_group(self, sheet_name):
        vol_group_mapping = {
            "Volume Group Number": "volume_group_number",
            "Volume Group  Name": "volume_group_name",
            "Number of Campus Locations": "number_of_campus_locations",
        }
        vol_group_mapping.update(self.generic_column_mapping)

        volume_group = self.read_xl_sheet(sheet_name)
        volume_group["original_info"] = volume_group.apply(
            self.get_original_info, axis=1
        )
        volume_group = volume_group.rename(columns=vol_group_mapping)
        volume_group_rec = volume_group.to_dict("records")
        migrate_bulk_data(apps, "pharmacy", "VolumeGroupSalesInfo", volume_group_rec)
        return volume_group

    def get_original_info(self, row):
        return json.dumps(row.to_dict())

    def read_xl_sheet(self, sheet_name):
        data_frame = pd.read_excel(self.xls, sheet_name, header=1)
        data_frame = data_frame.rename(columns=lambda x: x.strip())
        data_frame = data_frame.replace("#MULTIVALUE", None)
        if len(list(data_frame.iloc[-1])) > 0 and str(
            list(data_frame.iloc[-1])[0]
        ).__contains__("complimentary estimate from wholesaler"):
            data_frame = data_frame[:-2]
        return data_frame
