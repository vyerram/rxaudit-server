from http import HTTPMethod
from wsgiref.util import FileWrapper
from django.http import HttpResponseServerError, HttpResponse
from audit.constants import FileFormats
from core.utils import get_default_value_if_null, upload_file, get_object_or_none
from core.views import CoreViewset
from . import models, serializers
from pharmacy.constants import ProcessingStatusCodes
from pharmacy.utils import get_processing_status
from pharmacy.models import Pharmacy
from django.core.files.storage import FileSystemStorage
from django.core.files.base import ContentFile
from rest_framework.decorators import action
from .util import ProcessAuditData
from .util import batch_process_files
import os
from django.conf import settings
from rest_framework.response import Response
import threading
import pandas as pd
from core.utils import download_file
from django.forms.models import model_to_dict
from django.db import transaction
from rest_framework import status
from .util import handle_zip_file, log_error
import zipfile
from .models import ProcessLogHdr
from core.utils import get_boto3_client
import io
from django.db.models import Q


class PharmacyAuditDataviewset(CoreViewset):
    serializer_class = serializers.PharmacyAuditDataserializer
    queryset = models.PharmacyAuditData.objects.select_related(
        "pharmacy_pharmacyaudit"
    ).all()


class Distributorsviewset(CoreViewset):
    serializer_class = serializers.Distributorserializer
    queryset = models.Distributors.objects.all()


class DistributorAuditDataviewset(CoreViewset):
    serializer_class = serializers.DistributorAuditDataserializer
    queryset = models.DistributorAuditData.objects.select_related(
        "distributor", "process_log"
    ).all()


class FileDBMappingviewset(CoreViewset):
    serializer_class = serializers.FileDBMappingDataserializer
    queryset = models.FileDBMapping.objects.select_related(
        "distributor", "pharmacy", "pharmacy_software", "volume_group"
    ).all()

    def get_queryset(self):
        """
        Filter mappings based on pharmacy's volume group.
        Shows: Admin mappings (volume_group=null) + User's pharmacy's volume group mappings
        """
        queryset = super().get_queryset()
        user = self.request.user
        
        # Get query parameters
        pharmacy_software = self.request.query_params.get('pharmacy_software')
        distributor = self.request.query_params.get('distributor')
        
        # Base filter: Always include admin mappings (volume_group=null)
        filters = Q(volume_group__isnull=True)
        
        # Add pharmacy's volume group mappings
        # This works for BOTH pharmacy users AND volume group users
        if hasattr(user, 'pharmacy') and user.pharmacy and user.pharmacy.volume_group:
            filters |= Q(volume_group=user.pharmacy.volume_group)
        
        queryset = queryset.filter(filters)
        
        # Apply additional filters
        if pharmacy_software:
            queryset = queryset.filter(pharmacy_software_id=pharmacy_software)
        if distributor:
            queryset = queryset.filter(distributor_id=distributor)
            
        return queryset

    def perform_create(self, serializer):
        """
        Auto-assign volume_group from user's pharmacy when creating mappings.
        Admin (no pharmacy) → volume_group=null (visible to all)
        User with pharmacy → volume_group=pharmacy's volume group
        """
        user = self.request.user
        volume_group = None
        
        # Get volume group from user's pharmacy
        if hasattr(user, 'pharmacy') and user.pharmacy and user.pharmacy.volume_group:
            volume_group = user.pharmacy.volume_group
        
        serializer.save(volume_group=volume_group)

    def perform_update(self, serializer):
        """
        Ensure users can only update mappings from their pharmacy's volume group.
        Admins (no pharmacy) can update all mappings.
        """
        user = self.request.user
        instance = self.get_object()
        
        # Only validate if updating a volume group mapping
        if instance.volume_group:
            # Get user's pharmacy's volume group
            user_volume_group = None
            if hasattr(user, 'pharmacy') and user.pharmacy and user.pharmacy.volume_group:
                user_volume_group = user.pharmacy.volume_group
            
            # Check permission
            if instance.volume_group != user_volume_group:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("Cannot modify mappings from other volume groups")
        
        serializer.save()
    
    @action(detail=False, methods=[HTTPMethod.POST])
    def get_file_columns(self, request):
        try:
            data = request.data
            file = data.get("file")
            file_name = file.name
            process_name = data.get("process_name", "temp")  # Get process name from request
            file_location = os.path.join(os.getcwd(), settings.AUDIT_FILES_LOCATION, process_name)
            os.makedirs(file_location, exist_ok=True)  # Create folder if doesn't exist
            fs = FileSystemStorage(file_location)
            fs.save(file_name, ContentFile(file.read()))
            full_file_name = os.path.join(file_location, file_name)
            name, extension = os.path.splitext(full_file_name)
            df = None
            if extension == FileFormats.CSV.value:
                df = pd.read_csv(full_file_name)
            elif (
                extension == FileFormats.XLSX.value
                or extension == FileFormats.XLS.value
            ):
                xls = pd.ExcelFile(full_file_name)
                df = pd.read_excel(xls)
                xls.close()
            if df is not None:
                output_cols = []
                if len(df.columns) > 2 and not any(
                    pd.isna(val) or "Unnamed" in val for val in df.columns
                ):
                    output_cols = list(df.columns)
                else:
                    for i, row in df.iterrows():
                        if len(row.values) > 2 and not any(
                            pd.isna(val) for val in row.values
                        ):
                            output_cols = list(row.values)
                            break
                return Response(data=output_cols)
            else:
                return HttpResponseServerError(
                    "Please contact admin to resolve the error"
                )
        except Exception as e:
            return HttpResponseServerError(
                "Unable to get the columns, Please clean the file. "
            )

        finally:
            if os.path.exists(full_file_name):
                os.remove(full_file_name)

    @action(detail=False, methods=["GET"])
    def check_mapped_columns(self, request):
        pharmacy_software = request.query_params.get("pharmacy_software", None)

        if not pharmacy_software:
            return Response(
                {"valid": "no", "detail": "Pharmacy Software ID is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        mappings = models.FileDBMapping.objects.filter(
            pharmacy_software=pharmacy_software
        )

        if mappings.exists():
            return Response({"valid": "yes"}, status=status.HTTP_200_OK)

        get_columns_response = self.get_file_columns(request)

        if get_columns_response.status_code == status.HTTP_200_OK:
            columns = get_columns_response.data
            if columns:
                return Response({"valid": "yes"}, status=status.HTTP_200_OK)
        return Response({"valid": "no"}, status=status.HTTP_200_OK)


class FileTypeviewset(CoreViewset):
    serializer_class = serializers.FileTypeserializer
    queryset = models.FileType.objects.all()


class PaymentMethodviewset(CoreViewset):
    serializer_class = serializers.PaymentMethodserializer
    queryset = models.PaymentMethod.objects.all()


class ClaimStatusviewset(CoreViewset):
    serializer_class = serializers.ClaimStatusserializer
    queryset = models.ClaimStatus.objects.all()


class ProcessLogHdrviewset(CoreViewset):
    serializer_class = serializers.ProcessLogHdrserializer
    queryset = models.ProcessLogHdr.objects.prefetch_related(
        "process_log_detail_process_log"
    ).all()

    @action(detail=True, methods=[HTTPMethod.POST])
    def reprocess_failed(self, request, pk):
        """
        Reprocesses failed files with uploaded files.
        Supports manual re-upload (ZIP or individual files).
        """
        try:
            process_log = self.get_object()
            pharmacy = request.data.get("pharmacy")

            process_folder = os.path.join(settings.AUDIT_FILES_LOCATION, process_log.name)
            os.makedirs(process_folder, exist_ok=True)
            
            # Set status to in-progress
            process_log.status = get_processing_status(ProcessingStatusCodes.Inprogress.value)
            process_log.save(update_fields=["status"])

            uploaded_files = request.FILES.getlist("file")
            
            if not uploaded_files:
                return Response(
                    {"error": "No files provided for reprocessing"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check if any uploaded file is a ZIP
            is_zip = any(
                f.name.endswith(".zip") or f.content_type == "application/zip"
                for f in uploaded_files
            )

            if is_zip:
                # Take the first ZIP
                zip_file = next(f for f in uploaded_files if f.name.endswith(".zip"))
                t = threading.Thread(
                    target=handle_zip_file,
                    args=[zip_file, process_log, process_log, pharmacy, True],
                    daemon=True,
                )
                t.start()
                return Response(
                    {"message": "Uploaded ZIP accepted. Reprocessing started."},
                    status=status.HTTP_200_OK,
                )

            # Otherwise multiple single files (xlsx/csv)
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in uploaded_files:
                    zf.writestr(f.name, f.read())
            zip_buffer.seek(0)
            
            t = threading.Thread(
                target=handle_zip_file,
                args=[zip_buffer, process_log, process_log, pharmacy, True],
                daemon=True,
            )
            t.start()
            return Response(
                {"message": f"Uploaded {len(uploaded_files)} files reprocessing started."},
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            log_error(
                process_log=pk,
                error_message=str(e),
                error_type="Reprocess Failed",
                error_severity_code="ER",
                error_location="reprocess_failed",
            )
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def get_queryset(self):
            """
            Filter queryset based on user permissions
            """
            queryset = super().get_queryset()
            request_user = self.request.user
            
            if request_user.pharmacy:
                queryset = queryset.filter(
                    process_log_detail_process_log__pharmacy=request_user.pharmacy
                ).distinct()
                
            elif request_user.volume_group:
                pharmacy_ids = list(Pharmacy.objects.filter(
                    volume_group=request_user.volume_group
                ).values_list("id", flat=True))
                
                if pharmacy_ids:
                    queryset = queryset.filter(
                        process_log_detail_process_log__pharmacy__in=pharmacy_ids
                    ).distinct()
                
            return queryset

    @action(detail=True, methods=[HTTPMethod.POST])
    def execute(self, request, **kwargs):
        obj = self.get_object()
        try:
            obj.status = get_processing_status(ProcessingStatusCodes.Inprogress.value)
            obj.save()
            process_audit_data = ProcessAuditData()
            t = threading.Thread(
                target=process_audit_data.trigger_process,
                args=[obj],
                daemon=True,
            )
            t.start()
            return Response(
                "Triggered process execution, check this space in few minutes"
            )
        except Exception as e:
            obj.status = get_processing_status(ProcessingStatusCodes.Failure.value)
            obj.log = str(e)
            obj.save()
            return HttpResponseServerError(
                "Comparision process failed due to " + str(e)
            )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Clean up S3 files before deleting DB records
        from .util import cleanup_s3_folder
        cleanup_s3_folder(instance.name)
        
        # Delete related records
        instance.process_log_detail_process_log.all().delete()
        instance.pharmacy_process_log.all().delete()
        instance.distributor_process_log.all().delete()
        instance.error_log_process_log.all().delete()
        instance.delete()   
         
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=[HTTPMethod.GET])
    def download_file(self, request, pk):
        obj = self.get_object()
        
        if not obj.output_file:
            return Response(
                {"error": "No output file available"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        object_key = obj.output_file.replace(f"{settings.AWS_BUCKET}/", "")
        
        from core.utils import get_s3_file_location
        download_url = get_s3_file_location(settings.AWS_BUCKET, object_key)
        
        # ✅ Return JSON instead of redirect
        return Response({"download_url": download_url}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=[HTTPMethod.POST])
    def automation_process(self, request, pk):
        try:
            process_log = ProcessLogHdr.objects.get(pk=pk)
            obj = process_log

            # <<<< IMMEDIATELY SET STATUS TO IN PROGRESS >>>>
            with transaction.atomic():
                obj.status = get_processing_status(ProcessingStatusCodes.Inprogress.value)
                obj.save(update_fields=["status"])  # <<<< Save immediately so UI sees "In Progress"

            process_folder = os.path.join(settings.AUDIT_FILES_LOCATION, obj.name)
            os.makedirs(process_folder, exist_ok=True)
        
            # Check if this is a resubmission
            is_resubmission = request.data.get("is_resubmission", "false").lower() == "true"

            if not is_resubmission:
                # Reset counters for initial run
                obj.failed_files_json = "[]"
                obj.failed_count = 0
                obj.pharmacy_processed_count = 0
                obj.pharmacy_failed_count = 0
                obj.distributor_processed_count = 0
                obj.distributor_failed_count = 0
                obj.save() 

            data = request.data
            uploaded_files = request.FILES.getlist("file")

            if not uploaded_files:
                raise Exception("No files provided")
            
            is_zip = False
            for uploaded_file in uploaded_files:
                if (
                    uploaded_file.name.endswith(".zip")
                    or uploaded_file.content_type == "application/zip"
                ):
                    is_zip = True
                    zip_file = uploaded_file
                    break

            if is_zip:
                t = threading.Thread(
                    target=handle_zip_file,
                    args=[
                        zip_file,
                        process_log,
                        obj,
                        data.get("pharmacy"),
                        is_resubmission,
                    ],
                    daemon=True,
                )
                t.start()
            else:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    for uploaded_file in uploaded_files:
                        zip_file.writestr(uploaded_file.name, uploaded_file.read())
                zip_buffer.seek(0)
                pharmacy = data.get("pharmacy")
                t = threading.Thread(
                    target=handle_zip_file,
                    args=[zip_buffer, process_log, obj, pharmacy, is_resubmission],
                    daemon=True,
                )
                t.start()

            return Response({"message": "Process Triggered"}, status=status.HTTP_200_OK)

        except ProcessLogHdr.DoesNotExist:
            log_error(
                error_message=f"ProcessLog with ID {pk} does not exist",
                error_type="Validation Error",
                error_severity_code="CR",
                error_location="automation_process",
            )
            return Response(
                {"error": f"ProcessLog with ID {pk} does not exist"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=[HTTPMethod.GET])
    def get_progress(self, request, pk):
        """
        Returns current progress for polling.
        """
        try:
            obj = self.get_object()
            return Response({
                "status": obj.status.description if obj.status else "Unknown",
                "pharmacy_processed_count": obj.pharmacy_processed_count or 0,
                "pharmacy_failed_count": obj.pharmacy_failed_count or 0,
                "distributor_processed_count": obj.distributor_processed_count or 0,
                "distributor_failed_count": obj.distributor_failed_count or 0,
                "failed_files_json": obj.failed_files_json or "[]",
                "output_file": obj.output_file or None,
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ProcessLogDetailviewset(CoreViewset):
    serializer_class = serializers.ProcessLogDetailserializer
    queryset = models.ProcessLogDetail.objects.select_related("process_log").all()

    @action(detail=True, methods=[HTTPMethod.GET])
    def download_file(self, request, pk):
        obj = self.get_object()
        
        if not obj.file_url:
            return Response(
                {"error": "No file available"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        object_key = obj.file_url.replace(f"{settings.AWS_BUCKET}/", "")
        
        from core.utils import get_s3_file_location
        download_url = get_s3_file_location(settings.AWS_BUCKET, object_key)
        
        # ✅ Return JSON instead of redirect
        return Response({"download_url": download_url}, status=status.HTTP_200_OK)

    @action(detail=False, methods=[HTTPMethod.POST])
    def add_log(self, request):
        try:
            data = request.data
            file_name = data.get("file_name")
            aws_file_url = data.get("download_url")
            process_name = data.get("process_name")
            process_log_hdr = models.ProcessLogHdr.objects.get_or_create(
                name=process_name
            )[0]
            distributor = data.get("distributor")
            pharmacy = data.get("pharmacy")
            full_file_url = f"{settings.AWS_BUCKET}/{aws_file_url}"
            process_log_detail = models.ProcessLogDetail.objects.create(
                file_type=models.FileType.objects.get(id=data.get("file_type")),
                file_name=file_name,
                process_log=process_log_hdr,
                file_url=full_file_url,
                distributor=get_object_or_none(
                    models.Distributors,
                    pk=get_default_value_if_null(distributor, None),
                ),
                pharmacy=get_object_or_none(
                    models.Pharmacy,
                    pk=get_default_value_if_null(pharmacy, None),
                ),
            )
            response_data = model_to_dict(process_log_detail)
            response_data["id"] = process_log_detail.id

            return Response(data=response_data)
        except Exception as e:
            return HttpResponseServerError("Failed due to " + str(e))

    @action(detail=False, methods=[HTTPMethod.POST])
    def validate_file(self, request):
        try:
            data = request.data
            file = data.get("file")
            distributor = data.get("distributor")
            pharmacy = data.get("pharmacy")
            process_audit_data = ProcessAuditData()
            file_name = file.name
            process_name = data.get("process_name", "temp")
            file_location = os.path.join(os.getcwd(), settings.AUDIT_FILES_LOCATION, process_name)
            os.makedirs(file_location, exist_ok=True)
            fs = FileSystemStorage(file_location)
            fs.save(file_name, ContentFile(file.read()))
            full_file_name = os.path.join(file_location, file_name)
            is_valid_headers, invalid_hdrs = process_audit_data.validate_headers(
                full_file_name, distributor, pharmacy
            )
            if not is_valid_headers:
                return HttpResponseServerError(
                    "Missing headers in uploaded file: " + str(invalid_hdrs)
                )
            is_valid_file, invalid_ndcs = process_audit_data.validate_file(
                full_file_name, distributor, pharmacy
            )
            if not is_valid_file:
                return HttpResponseServerError(
                    "Invalid Pack size data for NDCs detected " + str(invalid_ndcs)
                )

            return Response("File is valid")
        except Exception as e:
            return HttpResponseServerError("File validation failed due to: " + str(e))
        finally:
            if os.path.exists(full_file_name):
                os.remove(full_file_name)


class BinNumbersviewset(CoreViewset):
    serializer_class = serializers.BinNumbersSerializers
    queryset = models.BinNumbers.objects.all()

    @action(detail=False, methods=[HTTPMethod.POST])
    def upload_file(self, request):
        try:
            data = request.data
            file = data.get("file")
            bin_group_id = data.get("bin_groups")
            bin_group = models.BinGroups.objects.get(id=bin_group_id)
            df = pd.read_excel(file)
            bin_numbers = set(df[df.columns[0]].dropna().tolist())
            with transaction.atomic():
                models.BinNumbers.objects.filter(bin_groups=bin_group_id).delete()
                bin_number_objects = [
                    models.BinNumbers(number=number, bin_groups=bin_group)
                    for number in bin_numbers
                ]
                models.BinNumbers.objects.bulk_create(bin_number_objects)
            updated_bin_numbers = models.BinNumbers.objects.filter(bin_groups=bin_group)
            serializer = serializers.BinNumbersSerializers(
                updated_bin_numbers, many=True
            )
            return Response(serializer.data)

        except Exception as e:
            return HttpResponseServerError("File upload failed due to " + str(e))


class BinGroupsviewset(CoreViewset):
    serializer_class = serializers.BinGroupsSerializers
    queryset = models.BinGroups.objects.prefetch_related("binnumber_bingroup").all()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.binnumber_bingroup.all().delete()
        super().perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CleanFilesLogviewset(CoreViewset):
    serializer_class = serializers.CleanFilesLogserializer
    queryset = models.CleanFilesLog.objects.all()

    @action(detail=True, methods=[HTTPMethod.GET])
    def download_file(self, request, pk):
        obj = self.get_object()
        bucket, object_name = obj.output_file_url.split("/", 1)
        output_file_name = os.path.basename(object_name)
        full_file_name = os.path.join(
            os.getcwd(), settings.CLEAN_FILES_LOCATION, output_file_name
        )
        s3_client = get_boto3_client()
        file_location = os.path.join(os.getcwd(), settings.CLEAN_FILES_LOCATION)
        response = s3_client.download_file(
            settings.AWS_BUCKET, object_name, full_file_name
        )
        name, extension = os.path.splitext(full_file_name)
        with open(full_file_name, "rb") as output_content:
            content_type = "text/csv"
            if extension == ".xls":
                content_type = "application/vnd.ms-excel"
            elif extension == ".xlsx":
                content_type = (
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            elif extension == ".zip":
                content_type = "application/zip"
            response = HttpResponse(
                FileWrapper(output_content), content_type=content_type
            )
        os.remove(full_file_name)
        return response

    @action(detail=True, methods=[HTTPMethod.POST])
    def clean_file(self, request, pk):
        try:
            obj = self.get_object()
            obj.status = get_processing_status(ProcessingStatusCodes.Inprogress.value)
            obj.save()
            data = request.data
            file = data.get("file")
            file_name = file.name
            output_file_name = "cleaned_" + file_name
            file_location = os.path.join(
                os.getcwd(), settings.CLEAN_FILES_LOCATION, obj.name
            )
            fs = FileSystemStorage(file_location)
            fs.save(file_name, ContentFile(file.read()))
            t = threading.Thread(
                target=batch_process_files,
                args=[file_location, file_name, file, obj, output_file_name],
                daemon=True,
            )
            t.start()
            return Response({"message": "Process Triggered"}, status=status.HTTP_200_OK)
        except Exception as e:
            return HttpResponseServerError("File cleaning failed due to: " + str(e))


class Errorlogsviewset(CoreViewset):
    serializer_class = serializers.ErrorLogserializer
    queryset = models.ErrorLogs.objects.all()


class ErrorSeverityviewset(CoreViewset):
    serializer_class = serializers.ErrorSeverityserializer
    queryset = models.ErrorSeverity.objects.all()