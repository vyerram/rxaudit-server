from datetime import datetime
import json
from django.apps import apps
from core.utils import get_default_value_if_null, migrate_bulk_data
import pandas as pd
import os
from pharmacy.models import Pharmacy, ProcessingStatus, VolumeGroup

duplicate_column_in_rebateInfo = "Monthly Source Admin Fee"


def get_original_info(row):
    return json.dumps(row.to_dict())


class ProcessAllwinDailyFile:

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

        self.ignore_list = ["Ship to Affiliation Level3 Customer Name_Current Version"]

    def process_daily_report(self, xls):
        self.xls = xls
        self.reporting_period_start, self.reporting_period_end = (
            self.save_group_summary("Summary for Buying Group")
        )
        self.save_account_mtd("By Account MTD")
        self.save_volume_group("Volume Group MTD")

    def save_group_summary(self, sheet_name):
        summary = {}
        group_summary = self.read_xl_sheet(sheet_name)
        if "Level 1 Group" in list(group_summary.columns):
            group_summary = self.read_xl_sheet(sheet_name, no_headers=True)
        summary["original_info"] = json.loads(group_summary.to_json(orient="records"))
        column_keys = ["group_key", "group_val", ""]
        if len(group_summary.columns) == 2:
            group_summary.columns = column_keys[:-1]
        elif len(group_summary.columns) == 3:
            group_summary.columns = column_keys
        for index, summary_rec in group_summary.iterrows():
            if summary_rec["group_key"] == "Level 1 Group":
                summary["group_name"] = summary_rec["group_val"]
                summary["group__name"] = summary_rec["group_val"]
            elif summary_rec["group_key"] == "Reporting Period":
                reporting_period_start, reporting_period_end = map(
                    str.strip, summary_rec["group_val"].split("-")
                )
                if reporting_period_start and reporting_period_end:
                    summary["reporting_period_start"] = datetime.strptime(
                        reporting_period_start, "%m/%d/%y"
                    ).strftime("%Y-%m-%d")
                    summary["reporting_period_end"] = datetime.strptime(
                        reporting_period_end, "%m/%d/%y"
                    ).strftime("%Y-%m-%d")
                else:
                    file_name = os.path.basename(self.xls.io)
                    date = datetime.strptime(file_name.split("_")[0], "%Y-%m-%d")
                    summary["reporting_period_start"] = date
                    summary["reporting_period_end"] = date
            elif summary_rec["group_key"] in self.generic_column_mapping.keys():
                summary[self.generic_column_mapping[summary_rec["group_key"]]] = (
                    summary_rec["group_val"]
                )

        migrate_bulk_data(apps, "pharmacy", "GroupSalesInfo", [summary])
        return summary["reporting_period_start"], summary["reporting_period_end"]

    def save_account_mtd(self, sheet_name):
        mtd_column_mapping = {
            "Affiliation Level 3 Number": "affiliation_level3_number",
            "Affiliation Level 3 Name": "affiliation_level3_name",
            "Affiliation Level 3 Number - Current Version": "affiliation_level3_number",
            "Affiliation Level 3 Name - Current Version": "affiliation_level3_name",
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
            get_original_info, axis=1
        )
        pharmacy_account_mtd = pharmacy_account_mtd.rename(columns=mtd_column_mapping)
        pharmacy_account_mtd["pharmacy"] = pharmacy_account_mtd.apply(
            self.get_pharmacy, axis=1
        )
        pharmacy_account_mtd["reporting_period_start"] = self.reporting_period_start
        pharmacy_account_mtd["reporting_period_end"] = self.reporting_period_end
        pharmacy_account_mtd_rec = pharmacy_account_mtd.to_dict("records")
        migrate_bulk_data(
            apps, "pharmacy", "PharmacySalesInfo", pharmacy_account_mtd_rec
        )
        return pharmacy_account_mtd

    def get_pharmacy(self, row):
        pharmacy = Pharmacy.objects.filter(
            campus_master=int(get_default_value_if_null(row["campus_number"], 0))
        )
        if len(pharmacy) > 0:
            return pharmacy.first()
        else:
            return None

    def save_volume_group(self, sheet_name):
        vol_group_mapping = {
            "Volume Group Number": "volume_group_number",
            "Volume Group  Name": "volume_group_name",
            "Number of Campus Locations": "number_of_campus_locations",
        }
        vol_group_mapping.update(self.generic_column_mapping)

        volume_group = self.read_xl_sheet(sheet_name)
        for col in self.ignore_list:
            if col in volume_group.columns:
                volume_group = volume_group.drop([col], axis=1)
        volume_group["original_info"] = volume_group.apply(get_original_info, axis=1)
        volume_group = volume_group.rename(columns=vol_group_mapping)
        volume_group["volumegroup"] = volume_group.apply(self.get_volumn_group, axis=1)
        volume_group["reporting_period_start"] = self.reporting_period_start
        volume_group["reporting_period_end"] = self.reporting_period_end
        volume_group_rec = volume_group.to_dict("records")
        migrate_bulk_data(apps, "pharmacy", "VolumeGroupSalesInfo", volume_group_rec)
        return volume_group

    def get_volumn_group(self, row):
        volumn_group = VolumeGroup.objects.filter(
            number=int(get_default_value_if_null(row["volume_group_number"], 0))
        )
        if len(volumn_group) > 0:
            volumn_group = volumn_group.first()
            volumn_group.name = row["volume_group_name"]
            volumn_group.location_count = row["number_of_campus_locations"]
            volumn_group.save()
            return volumn_group

    def read_xl_sheet(self, sheet_name, no_headers=False):
        data_frame = pd.read_excel(self.xls, sheet_name)
        if no_headers:
            data_frame = pd.read_excel(self.xls, sheet_name, header=None)
        data_frame = data_frame.replace("#MULTIVALUE", None)
        if len(list(data_frame.iloc[-1])) > 0 and str(
            list(data_frame.iloc[-1])[0]
        ).__contains__("complimentary estimate from wholesaler"):
            data_frame = data_frame[:-2]
        return data_frame


class ProcessRebateData:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def process_rebates_report(self, xls):
        self.xls = xls
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
            "Monthly Source Admin Fee.1": "monthly_source_admin_fee_amt",
        }
        self.ignore_list = ["DIV", "Sales Rep Name"]
        rebate_summary = self.read_xl_sheet(xls.sheet_names[0])

        rebate_summary["original_info"] = rebate_summary.apply(
            get_original_info, axis=1
        )
        if duplicate_column_in_rebateInfo in rebate_summary:
            rebate_summary.fillna(0, inplace=True)
            admin_fee_columns = [
                col
                for col in rebate_summary.columns
                if duplicate_column_in_rebateInfo in col
            ]
            selected_column = None
            for column in admin_fee_columns:
                if (rebate_summary[column] < 1).all():
                    selected_column = column
                    break
            if selected_column:
                rebate_summary.rename(
                    columns={selected_column: "monthly_source_admin_fee_pct"},
                    inplace=True,
                )
        for col in self.ignore_list:
            if col in rebate_summary.columns:
                rebate_summary = rebate_summary.drop([col], axis=1)
        rebate_summary = rebate_summary.rename(columns=rebate_columns)
        rebate_summary["pharmacy"] = rebate_summary.apply(self.get_pharmacy, axis=1)
        rebate_summary_rec = rebate_summary.to_dict("records")
        migrate_bulk_data(apps, "pharmacy", "RebateInfo", rebate_summary_rec)

    def get_pharmacy(self, row):
        pharmacy = Pharmacy.objects.filter(
            campus_master=int(get_default_value_if_null(row["campus_number"], 0))
        )
        if len(pharmacy) > 0:
            return pharmacy.first()
        else:
            return None

    def read_xl_sheet(self, sheet_name):
        data_frame = pd.read_excel(self.xls, sheet_name, header=1)
        data_frame = data_frame.rename(columns=lambda x: x.strip())
        data_frame = data_frame.replace("#MULTIVALUE", None)
        return data_frame


def get_processing_status(code):
    try:
        status = ProcessingStatus.objects.filter(code=code).first()
        return status
    except Exception as e:
        return None
