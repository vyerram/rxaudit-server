from django.core.management.base import BaseCommand, CommandError
import numpy as np
import pandas as pd
import os
from django.conf import settings
from django.db import connection
from core.utils import get_sql_alchemy_conn


class Command(BaseCommand):

    def f(self, x):
        # c = x.columns.get_level_values(0)
        distributor_total = x.sum(axis=1)
        x["Total"] = distributor_total
        pharmacy_quantity = x.index._get_level_values(4)[0]
        x["Difference"] = distributor_total - pharmacy_quantity
        return x

    def format_NDC(self, x):
        if x and x != str(None):
            if len(x) < 11:
                x = "".join(str(0) for i in range(11 - len(x))) + x
            return x[:5] + "-" + x[5:9] + "-" + x[9:11]

    def handle(self, **options):
        try:
            # sql_statement = """SELECT * FROM (select pad_ndc,pad_brand,pad_strength,pad_quantity,pad_drug_name, sum(pad_quantity) as pharmacy_quantity from public."OPT_PAD_PharmacyAuditData" group by pad_ndc,pad_brand,pad_strength,pad_quantity,pad_drug_name) AS pharmacy_data
            #                     left outer join (select dad_ndc,description, sum(dad_quantity) as distributor_quantity from "OPT_DAD_DistributorAuditData" join "OPT_DTB_Distributors" on "OPT_DTB_Distributors".id = dad_distributor group by dad_ndc, description) AS distributor_data
            #                     on pharmacy_data.pad_ndc = distributor_data.dad_ndc"""
            # df = pd.read_sql_query(sql_statement, con=connection)

            # table = pd.pivot_table(
            #     df,
            #     values="distributor_quantity",
            #     index=[
            #         "pad_ndc",
            #         "pad_brand",
            #         "pad_strength",
            #         "pad_quantity",
            #         "pad_drug_name",
            #     ],
            #     columns=["description"],
            #     aggfunc="sum",
            #     # dropna=False,
            #     fill_value=0,
            # )
            sql_statement = f"""SELECT * FROM (select pad_ndc as "NDC",pad_brand as "Brand",pad_strength as "Strength",pad_size as "Size",pad_drug_name as "Drug Name", sum(pad_quantity) as "Quantity" from public."OPT_PAD_PharmacyAuditData"  where pad_process_log_id = '321b5573-b7e6-4b7a-af6a-4516d852f7d3' group by pad_ndc,pad_brand,pad_strength,pad_drug_name,pad_size) AS pharmacy_data
                                left outer join (select dad_ndc,description, sum(dad_quantity) as distributor_quantity from "OPT_DAD_DistributorAuditData" join "OPT_DTB_Distributors" on "OPT_DTB_Distributors".id = dad_distributor where dad_process_log_id = '321b5573-b7e6-4b7a-af6a-4516d852f7d3' group by dad_ndc, description) AS distributor_data 
                                on pharmacy_data."NDC" = distributor_data.dad_ndc"""
            df = pd.read_sql_query(sql_statement, con=get_sql_alchemy_conn())
            df["NDC"] = df["NDC"].astype(str).apply(lambda x: self.format_NDC(x))
            df["dad_ndc"] = (
                df["dad_ndc"].astype(str).apply(lambda x: self.format_NDC(x))
            )
            df = df.fillna(0)
            table = pd.pivot_table(
                df,
                values="distributor_quantity",
                index=[
                    "NDC",
                    "Brand",
                    "Drug Name",
                    "Strength",
                    "Quantity",
                    "Size",
                ],
                columns=["description"],
                aggfunc="sum",
            )
            table = table.drop(0, axis=1)
            table = table.fillna(0)
            table = table.groupby(level=0, group_keys=False).apply(self.f)
            file_name = f"test_sctipt_big_file.xlsx"
            full_file_name = os.path.join(
                os.getcwd(), settings.AUDIT_FILES_LOCATION, file_name
            )
            # table = table.style.map(self.highlight, subset=["Difference"])
            table.to_excel(full_file_name)
        except Exception as e:
            raise CommandError(e)
