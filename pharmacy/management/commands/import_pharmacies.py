import pandas as pd

from django.core.management.base import BaseCommand, CommandError
from django.apps import apps
from core.migrations.utilities.util import migrate_bulk_data

from django.db import transaction


class Command(BaseCommand):
    help = "Helps import pharmacies data"
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument(
            "--excel",
            type=str,
            help="Input of excel from which code needs to be generated.",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def handle(self, **options):
        try:
            column_mapping = {
                "SAP Ship To #": "sap_ship_to_no",
                "Volume Group": "volume_group_num",
                "Campus Master": "campus_master",
                "Name": "corp_name",
                "Address": "address__line1",
                "City": "address__city",
                "State": "address__state",
                "Zip": "address__zip",
                "Telephone": "phone",
                "Fax": "fax",
                "Affiliation #1 Name": "affiliation_1_name",
                "Affiliation #2 Name": "affiliation_2_name",
                "DEA#": "dea",
                "NPI": "npi",
                "GLN": "gln",
                "DBA": "dba",
                "PharmacyEmail": "email",
                "StateLicense": "state_license",
                "NCPA": "ncpa",
                "PrincipalName": "principal_name",
                "PrincipalCell": "principal_cell",
                "PrincipalEmail": "principal_email",
                "SalesContactPhone": "sales_contact__phone",
                "SalesContactCell": "sales_contact__cell",
                "SalesContactEmail": "sales_contact__email",
            }
            pharmacies = pd.ExcelFile(options["excel"])
            pharmacies_df = pd.read_excel(pharmacies, "pharmacies")
            pharmacies_df = pharmacies_df.rename(columns=column_mapping)
            pharmacies_df["volume_group__number"] = pharmacies_df["volume_group_num"]
            int_cols = [
                "phone",
                "fax",
                "state_license",
                "npi",
                "principal_cell",
                "sap_ship_to_no",
                "volume_group_num",
                "campus_master",
                "address__zip",
            ]
            pharmacies_df[int_cols] = pharmacies_df[int_cols].fillna(0)
            for int_col in int_cols:
                pharmacies_df[int_col] = (
                    pharmacies_df[int_col]
                    .astype(str)
                    .str.replace(r"\D+", "", regex=True)
                    .str.strip()
                )
            pharmacies_df = pharmacies_df.fillna("")
            pharma_rec = pharmacies_df.to_dict("records")

            with transaction.atomic():
                migrate_bulk_data(apps, "pharmacy", "Pharmacy", pharma_rec)

        except Exception as e:
            raise CommandError(e)
