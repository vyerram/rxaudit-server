import json
from wsgiref.util import FileWrapper
from django.core.files.storage import FileSystemStorage
from rest_framework.permissions import IsAuthenticated
from django.core.files.base import ContentFile
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from core.utils import upload_file
from core.views import CoreViewset
from correspondence.models import Template
from correspondence.views import generate_document_for_template
from pharmacy.constants import ProcessingStatusCodes
from pharmacy.utils import (
    ProcessAllwinDailyFile,
    ProcessRebateData,
    get_processing_status,
)
from django.http import HttpResponse, JsonResponse
from . import models, serializers
from http import HTTPMethod
from rest_framework.decorators import api_view, permission_classes
import pandas as pd
import os
from django.conf import settings
from urllib.request import urlretrieve
from rest_framework.permissions import AllowAny
from rest_framework import status
from django.core.mail import EmailMessage
from django.db.models import Sum
from rest_framework.decorators import action
from person import models as person_models, serializers as person_serializers
from http import HTTPMethod
from django.core.mail import send_mail
import threading


class Pharmacyviewset(CoreViewset):
    serializer_class = serializers.Pharmacyserializer
    queryset = models.Pharmacy.objects.select_related(
        "address", "status", "sales_contact", "volume_group"
    ).all()

    def get_queryset(self):
        queryset = super().get_queryset()
        volume_group = self.request.query_params.get('volume_group')

        print(f"DEBUG: volume_group param = '{volume_group}'")
        print(f"DEBUG: query_params = {self.request.query_params}")

        if volume_group:
            print(f"DEBUG: Filtering by volume_group_id={volume_group}")
            queryset = queryset.filter(volume_group_id=volume_group)
            print(f"DEBUG: Filtered count = {queryset.count()}")
        else:
            print(f"DEBUG: No volume_group filter, returning all")

        return queryset

    def create(self, request, *args, **kwargs):
        data = request.data
        if "address" in data:
            addressserializer = person_serializers.Addressserializer(
                data=data.pop("address"), many=False
            )
            addressserializer.is_valid(raise_exception=True)
            address_obj = addressserializer.save()

        if "sales_contact" in data:
            sales_contactserializer = person_serializers.Personserializer(
                data=data.pop("sales_contact"), many=False
            )
            sales_contactserializer.is_valid(raise_exception=True)
            sales_contact_obj = sales_contactserializer.save()

        if "volume_group" in data:
            volume_groupserializer = serializers.VolumeGroupserializer(
                data=data.pop("volume_group"), many=False
            )
            volume_groupserializer.is_valid(raise_exception=True)
            volume_group_obj = volume_groupserializer.save()

        serializer = self.get_serializer(data=data, many=False)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        obj.address = address_obj
        obj.sales_contact = sales_contact_obj
        obj.volume_group = volume_group_obj
        obj.status = models.PharmacyStatus.objects.get(id=data.pop("status"))
        obj.save()
        obj = self.queryset.filter(id=obj.id)
        pharmacies_vals = obj.values(
            "volume_group__name",
            "is_kinray_lead",
            "is_cardinal_lead",
            "created_at__date",
            "corp_name",
            "dba",
            "address__line1",
            "phone",
            "fax",
            "email",
            "cell",
            "contact_name",
            "principal_name",
            "curr_primary_wholesaler",
            "curr_total_volume",
            "est_80_committed_amt",
            "hiv_volume",
            "expected_gcr_pct",
            "is_affiliated_member",
            "is_un_affiliated_member",
            "is_startup_pharma",
            "is_sub_group_member",
            "sub_group_name",
            "proposed_payment_terms",
        )
        pharmacies = pharmacies_vals.first()
        pharmacies["address__city_state_zip"] = obj[0].address.city_state_zip
        template_obj = Template.objects.get(template_form="add_new_pharmacy")
        output_location = generate_document_for_template(template_obj.id, [pharmacies])
        # email = EmailMessage(
        #     "New pharmacy application",
        #     "Hi, Attached is the new pharmacy application.",
        #     settings.EMAIL_HOST_USER,
        #     ["bharadwaja.vempati@aspyrlabs.com"],
        # )
        # email.attach_file(output_location)
        # email.send()
        response = HttpResponse(
            FileWrapper(open(output_location, "rb")), content_type="application/pdf"
        )
        return response

    @action(methods=[HTTPMethod.GET], detail=True)
    def get_pharmacy_pdf(self, request, pk):
        obj = self.queryset.filter(id=pk)
        pharmacies_vals = obj.values(
            "volume_group__name",
            "is_kinray_lead",
            "is_cardinal_lead",
            "created_at__date",
            "corp_name",
            "dba",
            "address__line1",
            "phone",
            "fax",
            "email",
            "cell",
            "contact_name",
            "principal_name",
            "curr_primary_wholesaler",
            "curr_total_volume",
            "est_80_committed_amt",
            "hiv_volume",
            "expected_gcr_pct",
            "is_affiliated_member",
            "is_un_affiliated_member",
            "is_startup_pharma",
            "is_sub_group_member",
            "sub_group_name",
            "proposed_payment_terms",
        )
        pharmacies = pharmacies_vals.first()
        pharmacies["address__city_state_zip"] = obj[0].address.city_state_zip
        template_obj = Template.objects.get(template_form="add_new_pharmacy")
        output_location = generate_document_for_template(template_obj.id, [pharmacies])
        response = HttpResponse(
            FileWrapper(open(output_location, "rb")), content_type="application/pdf"
        )
        return response

    @action(methods=[HTTPMethod.GET], detail=False)
    def get_data_campus_master(self, request):
        aggregate_values = [
            "source_compliance_pct_base_member",
            "source_compliance_pct_new_member",
            "total_sales",
            "rx_sales",
            "brand_rx_sales",
            "generic_rx_sales",
            "gpo_generic_sales",
            "source_sales",
            "source_override_sales",
            "net_source_sales",
            "generic_source_sales",
            "generic_source_overrides",
            "net_generic_source_sales",
            "antidiabetic_sales",
            "antidiabeticglp1_sales",
            "antipsychotic_sales",
            "spx_sales",
            "spx_hiv",
            "spx_hep_c",
            "spx_cancer",
            "spx_ra",
            "spx_ms",
            "spd_sales",
            "brand_rx_dropship_sales",
            "non_rx_sales",
        ]
        queryset = (
            models.PharmacySalesInfo.objects.all()
            .values("campus_number")
            .annotate(**{val: Sum(val) for val in aggregate_values})
        )
        aggregate_values.append("campus_number")
        queryset = queryset.values(*aggregate_values)
        return JsonResponse(list(queryset), safe=False)


class PharmacySalesInfoviewset(CoreViewset):
    serializer_class = serializers.PharmacySalesInfoserializer
    queryset = models.PharmacySalesInfo.objects.select_related("pharmacy").all()


class VolumeGroupSalesInfoviewset(CoreViewset):
    serializer_class = serializers.VolumeGroupSalesInfoserializer
    queryset = (
        models.VolumeGroupSalesInfo.objects.select_related("volumegroup")
        .prefetch_related("volumegroup__pharmacy_volumegroup_id")
        .all()
    )


class GroupSalesInfoviewset(CoreViewset):
    serializer_class = serializers.GroupSalesInfoserializer
    queryset = models.GroupSalesInfo.objects.select_related("group").all()


class VolumeGroupviewset(CoreViewset):
    serializer_class = serializers.VolumeGroupserializer
    queryset = models.VolumeGroup.objects.select_related("group").all()


class Groupviewset(CoreViewset):
    serializer_class = serializers.Groupserializer
    queryset = models.Group.objects.all()


class PharmacyStatusviewset(CoreViewset):
    serializer_class = serializers.PharmacyStatusserializer
    queryset = models.PharmacyStatus.objects.all()


class PharmacySoftwareviewset(CoreViewset):
    serializer_class = serializers.PharmacySoftwareserializer
    queryset = models.PharmacySoftware.objects.all()


class RebateInfoviewset(CoreViewset):
    serializer_class = serializers.RebateInfoserializer
    queryset = models.RebateInfo.objects.select_related("pharmacy").all()


class FileProcessingLogsviewset(CoreViewset):
    serializer_class = serializers.FileProcessingLogsserializer
    queryset = models.FileProcessingLogs.objects.all()


class ProcessingStatusviewset(CoreViewset):
    serializer_class = serializers.ProcessingStatusserializer
    queryset = models.ProcessingStatus.objects.all()


@api_view([HTTPMethod.POST])
@permission_classes([AllowAny])
def trigger_process_email(request, **kwargs):
    try:
        data = request.data
        subject = data.get("subject")
        file = data.get("attachment")
        if (
            subject.__contains__("ALL-WIN- Kinray_Source Comp 2 Calc Report_Daily")
            or subject.__contains__("All-Win -- Admin Fee & Rebate Files")
            or subject.__contains__("ALLWIN Kinray_Source Comp Report_Monthly")
        ):
            file_name = file._name
            file_location = os.path.join(os.getcwd(), settings.EMAIL_FILES_LOCATION)
            fs = FileSystemStorage(file_location)
            fs.save(file_name, ContentFile(file.read()))
            full_file_name = os.path.join(file_location, file_name)
            file_process_logs = models.FileProcessingLogs(
                file_name=file_name,
                status=get_processing_status(ProcessingStatusCodes.Inprogress.value),
            )
            file_process_logs.save()
            t = threading.Thread(
                target=process_emails,
                args=[subject, full_file_name, file_name, file_process_logs],
                daemon=True,
            )
            t.start()
        return Response(data={"status": "success"}, status=status.HTTP_200_OK)
    except Exception as e:
        file_process_logs.status = get_processing_status(
            ProcessingStatusCodes.Failure.value
        )
        return Response(data=str(e), status=status.HTTP_400_BAD_REQUEST)


def process_emails(subject, full_file_name, file_name, file_process_logs):
    try:
        upload_file(full_file_name)
        file_process_logs.file_location = f"{settings.AWS_BUCKET}/{file_name}"
        file_process_logs.save()
        xls = pd.ExcelFile(full_file_name)
        if xls.io.__contains__("ALL-WIN- Kinray"):
            process_allwin_daily_file = ProcessAllwinDailyFile()
            process_allwin_daily_file.process_daily_report(xls)
        elif xls.io.__contains__("All-Win -- Admin Fee & Rebate Files"):
            process_rebate_data_file = ProcessRebateData()
            process_rebate_data_file.process_rebates_report(xls)
        xls.close()
        os.remove(full_file_name)
        file_process_logs.status = get_processing_status(
            ProcessingStatusCodes.Success.value
        )
        file_process_logs.save(update_fields=["status"])
    except Exception as e:
        nl = "\n"
        file_process_logs.status = get_processing_status(
            ProcessingStatusCodes.Failure.value
        )
        file_process_logs.log = str(e)
        file_process_logs.save(update_fields=["status", "log"])
        subject = f"{file_name} processing failed"
        message = f"""Hi,{nl}{nl}{nl}Please review file {file_name} as it's processing failed due to error {str(e)}.{nl}{nl}{nl}Thanks,{nl}AllwinRx."""
        email_from = settings.EMAIL_HOST_USER
        file_processing_recipient_list = settings.EMAIL_FAILURE_NOTIFICATION_LIST
        send_mail(subject, message, email_from, file_processing_recipient_list)
