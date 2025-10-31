from http import HTTPMethod
from wsgiref.util import FileWrapper
from django.http import HttpResponseServerError, HttpResponse
from django.db import IntegrityError
from audit.constants import FileFormats
from core.utils import get_default_value_if_null, upload_file, get_object_or_none
from core.views import CoreViewset
from . import models, serializers
from pharmacy.constants import ProcessingStatusCodes
from pharmacy.utils import get_processing_status
from pharmacy.models import Pharmacy, VolumeGroup
from django.core.files.storage import FileSystemStorage
from django.core.files.base import ContentFile
from rest_framework.decorators import action
from rest_framework import status
from .util import ProcessAuditData
from .util import batch_process_files
import os
from django.conf import settings
from rest_framework.response import Response
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
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
from rest_framework.exceptions import PermissionDenied
from .tasks import process_zip_file_task
import tempfile

logger = logging.getLogger(__name__)

# Thread pool for background tasks (configurable pool size) - Deprecated, use Celery
executor = ThreadPoolExecutor(max_workers=settings.BACKGROUND_TASK_WORKERS if hasattr(settings, 'BACKGROUND_TASK_WORKERS') else 4)


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

    def create(self, request, *args, **kwargs):
        """
        Override create to ensure our custom perform_create is called.
        CoreViewset calls super().perform_create() which bypasses our logic.
        """
        try:
            bulk = isinstance(request.data, list)

            if not bulk:
                serializer = self.get_serializer(data=request.data, many=False)
            else:
                serializer = self.get_serializer(data=request.data, many=True)

            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)  # Call self.perform_create, not super()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except IntegrityError:
            return Response(
                status=status.HTTP_409_CONFLICT, data="DuplicateRecord exists"
            )

    def _is_superuser(self):
        """
        Check if the current user is a SuperUser/Admin.
        Returns True if user.is_superuser is True OR user.role.code == "SuperUser"
        """
        user = self.request.user
        if not user or not user.is_authenticated:
            return False

        # Check is_superuser flag
        if getattr(user, "is_superuser", False):
            return True

        # Check role code
        role = getattr(user, "role", None)
        if role:
            role_code = getattr(role, "code", None)
            if role_code == "SuperUser":
                return True

        return False

    @lru_cache(maxsize=128)
    def _get_user_context(self):
        """
        Get user context with role type and relevant IDs (cached).
        Returns dict with:
            - user_type: 'superuser', 'volume_group', or 'pharmacy'
            - pharmacy_id: pharmacy UUID if user is pharmacy user
            - volume_group_id: volume group UUID

        Priority: pharmacy > volume_group > superuser
        This ensures users with assigned pharmacy/volume_group are treated by their role,
        even if they have superuser permissions.
        """
        user = self.request.user
        logger.debug(f"Getting user context for {user.username if user.is_authenticated else 'Anonymous'}")

        # Get pharmacy ID first (highest priority)
        pharmacy_id = getattr(user, "pharmacy_id", None)
        if not pharmacy_id:
            pharmacy = getattr(user, "pharmacy", None)
            pharmacy_id = getattr(pharmacy, "id", None)

        # If user has pharmacy, they're a pharmacy user (highest priority)
        if pharmacy_id:
            # Resolve volume group for the pharmacy
            volume_group_id = None
            pharmacy_data = (
                Pharmacy.objects.filter(id=pharmacy_id)
                .values("volume_group_id", "volume_group_num")
                .first()
            )
            if pharmacy_data:
                volume_group_id = pharmacy_data.get("volume_group_id")
                if not volume_group_id:
                    volume_group_num = pharmacy_data.get("volume_group_num")
                    if volume_group_num not in (None, ""):
                        try:
                            normalized_number = int(volume_group_num)
                        except (TypeError, ValueError):
                            normalized_number = None

                        if normalized_number is not None:
                            match = (
                                VolumeGroup.objects.filter(number=normalized_number)
                                .values_list("id", flat=True)
                                .first()
                            )
                            if match:
                                volume_group_id = match

            return {
                "user_type": "pharmacy",
                "pharmacy_id": pharmacy_id,
                "volume_group_id": volume_group_id
            }

        # Check for user-assigned volume group (second priority)
        volume_group_id = getattr(user, "volume_group_id", None)

        if volume_group_id:
            return {
                "user_type": "volume_group",
                "pharmacy_id": None,
                "volume_group_id": volume_group_id
            }

        # Only treat as superuser if no pharmacy AND no volume_group assigned
        if self._is_superuser():
            return {
                "user_type": "superuser",
                "pharmacy_id": None,
                "volume_group_id": None
            }

        # Fallback: regular user with no special permissions
        return {
            "user_type": "superuser",  # Default to superuser for safety
            "pharmacy_id": None,
            "volume_group_id": None
        }

    def get_queryset(self):
        """
        Filter mappings based on user role:
        - SuperUser: See ALL mappings (admin + all volume groups + all pharmacies)
        - Volume Group User: See admin mappings + VG-level mappings (pharmacy=null only)
        - Pharmacy User: See admin mappings + their pharmacy's mappings + VG-level mappings
        """
        queryset = super().get_queryset()
        user_context = self._get_user_context()

        # Get query parameters
        pharmacy_software = self.request.query_params.get('pharmacy_software')
        distributor = self.request.query_params.get('distributor')

        logger.debug(f"User context: {user_context}, params: pharmacy_software={pharmacy_software}, distributor={distributor}")

        # SuperUser sees everything - no filtering
        if user_context["user_type"] == "superuser":
            pass  # No filtering, return all
        elif user_context["user_type"] == "volume_group":
            # Volume Group users see:
            # 1. Admin mappings (volume_group=null)
            # 2. Volume group-level mappings (volume_group=their VG AND pharmacy=null)
            volume_group_id = user_context.get("volume_group_id")
            filters = Q(volume_group__isnull=True)  # Admin mappings

            if volume_group_id:
                # Only VG-level mappings, not pharmacy-specific ones
                filters |= Q(volume_group_id=volume_group_id, pharmacy__isnull=True)

            queryset = queryset.filter(filters)
        elif user_context["user_type"] == "pharmacy":
            # Pharmacy users see:
            # 1. Admin mappings (volume_group=null)
            # 2. Their pharmacy's mappings (pharmacy=their pharmacy)
            # 3. Their VG-level mappings (volume_group=their VG AND pharmacy=null)
            pharmacy_id = user_context.get("pharmacy_id")
            volume_group_id = user_context.get("volume_group_id")

            filters = Q(volume_group__isnull=True)  # Admin mappings

            if pharmacy_id:
                # Their specific pharmacy mappings
                filters |= Q(pharmacy_id=pharmacy_id)

            if volume_group_id:
                # VG-level mappings (not pharmacy-specific)
                filters |= Q(volume_group_id=volume_group_id, pharmacy__isnull=True)

            queryset = queryset.filter(filters)

        # Apply additional filters
        if pharmacy_software:
            queryset = queryset.filter(pharmacy_software_id=pharmacy_software)
        if distributor:
            queryset = queryset.filter(distributor_id=distributor)

        return queryset

    def perform_create(self, serializer):
        """
        Auto-assign volume_group and pharmacy based on user role when creating mappings.
        - SuperUser: volume_group=null, pharmacy=null (admin mapping, visible to all)
        - Volume Group User: volume_group=user's VG, pharmacy=null (shared across VG)
        - Pharmacy User: volume_group=pharmacy's VG, pharmacy=user's pharmacy
        """
        user_context = self._get_user_context()
        validated = serializer.validated_data
        record_list = validated if isinstance(validated, list) else [validated]

        logger.info(f"Creating mappings: user_type={user_context['user_type']}, count={len(record_list) if isinstance(record_list, list) else 1}")

        # Identify the scope (pharmacy software / distributor) being overwritten
        scope_keys = set()
        for record in record_list:
            pharmacy_software = record.get("pharmacy_software")
            distributor = record.get("distributor")
            file_type = record.get("file_type")
            pharmacy = record.get("pharmacy")

            key = (
                getattr(pharmacy_software, "id", None),
                getattr(distributor, "id", None),
                getattr(file_type, "id", None),
                getattr(pharmacy, "id", None),
            )
            if any(key):
                scope_keys.add(key)

        with transaction.atomic():
            # Delete existing mappings for the same scope
            for pharmacy_software_id, distributor_id, file_type_id, pharmacy_id in scope_keys:
                scope_filter = Q()
                has_scope = False

                if pharmacy_software_id:
                    scope_filter &= Q(pharmacy_software_id=pharmacy_software_id)
                    has_scope = True
                if distributor_id:
                    scope_filter &= Q(distributor_id=distributor_id)
                    has_scope = True
                if file_type_id:
                    scope_filter &= Q(file_type_id=file_type_id)
                    has_scope = True

                if not has_scope:
                    continue

                # Add volume group and pharmacy filters based on user type
                if user_context["user_type"] == "superuser":
                    scope_filter &= Q(volume_group__isnull=True)
                    scope_filter &= Q(pharmacy__isnull=True)
                elif user_context["user_type"] == "volume_group":
                    volume_group_id = user_context.get("volume_group_id")
                    if volume_group_id:
                        scope_filter &= Q(volume_group_id=volume_group_id)
                        scope_filter &= Q(pharmacy__isnull=True)
                elif user_context["user_type"] == "pharmacy":
                    pharmacy_id = user_context.get("pharmacy_id")
                    volume_group_id = user_context.get("volume_group_id")
                    if pharmacy_id:
                        scope_filter &= Q(pharmacy_id=pharmacy_id)
                    if volume_group_id:
                        scope_filter &= Q(volume_group_id=volume_group_id)

                models.FileDBMapping.objects.filter(scope_filter).delete()

            # Create new mapping records
            model_cls = (
                serializer.child.Meta.model if serializer.many else serializer.Meta.model
            )
            user = self.request.user if self.request.user.is_authenticated else None
            instances = []

            for record in record_list:
                payload = dict(record)
                # Remove volume_group and pharmacy from payload to set them explicitly
                payload.pop("volume_group", None)
                payload.pop("pharmacy", None)
                payload.pop("volume_group_id", None)
                payload.pop("pharmacy_id", None)

                # Set volume_group and pharmacy based on user type
                if user_context["user_type"] == "superuser":
                    # SuperUser creates admin mappings - don't set volume_group_id or pharmacy_id
                    # Leaving them unset will make them NULL in the database
                    pass
                elif user_context["user_type"] == "volume_group":
                    # Volume Group user creates VG-level mappings
                    volume_group_id = user_context.get("volume_group_id")
                    if volume_group_id:
                        payload["volume_group_id"] = volume_group_id
                    # Don't set pharmacy_id - leaving it unset will make it NULL
                elif user_context["user_type"] == "pharmacy":
                    # Pharmacy user creates pharmacy-specific mappings
                    pharmacy_id = user_context.get("pharmacy_id")
                    volume_group_id = user_context.get("volume_group_id")
                    if pharmacy_id:
                        payload["pharmacy_id"] = pharmacy_id
                    if volume_group_id:
                        payload["volume_group_id"] = volume_group_id

                if user:
                    payload.setdefault("created_by", user)
                    payload.setdefault("updated_by", user)

                instance = model_cls.objects.create(**payload)
                instances.append(instance)

        serializer.instance = instances if serializer.many else instances[0]

    def perform_update(self, serializer):
        """
        Ensure users can only update their own mappings.
        - SuperUser: Can update all mappings
        - Volume Group User: Can only update their VG's mappings (not admin mappings)
        - Pharmacy User: Can only update their pharmacy's mappings (not admin mappings)
        """
        user_context = self._get_user_context()
        instance = self.get_object()

        # SuperUser can update anything
        if user_context["user_type"] == "superuser":
            pass  # Allow update
        else:
            # Non-superusers cannot update admin mappings
            if instance.volume_group is None:
                raise PermissionDenied("Cannot modify admin mappings")

            # Volume Group users can only update their own VG mappings
            if user_context["user_type"] == "volume_group":
                volume_group_id = user_context.get("volume_group_id")
                if instance.volume_group_id != volume_group_id:
                    raise PermissionDenied("Cannot modify mappings from other volume groups")
                if instance.pharmacy is not None:
                    raise PermissionDenied("Cannot modify pharmacy-specific mappings")

            # Pharmacy users can only update their own pharmacy mappings
            elif user_context["user_type"] == "pharmacy":
                pharmacy_id = user_context.get("pharmacy_id")
                volume_group_id = user_context.get("volume_group_id")

                if instance.volume_group_id != volume_group_id:
                    raise PermissionDenied("Cannot modify mappings from other volume groups")
                if instance.pharmacy_id != pharmacy_id:
                    raise PermissionDenied("Cannot modify mappings from other pharmacies")

        # Preserve volume_group and pharmacy on update
        kwargs = {
            "volume_group": instance.volume_group,
            "pharmacy": instance.pharmacy
        }
        user = self.request.user if self.request.user.is_authenticated else None
        if user and hasattr(instance, "updated_by"):
            kwargs["updated_by"] = user
        serializer.save(**kwargs)
    
    def perform_destroy(self, instance):
        """
        Restrict deletion based on user role:
        - SuperUser: Can delete all mappings
        - Volume Group User: Can only delete their VG's mappings (not admin mappings)
        - Pharmacy User: Can only delete their pharmacy's mappings (not admin mappings)
        """
        user_context = self._get_user_context()

        # SuperUser can delete anything
        if user_context["user_type"] == "superuser":
            pass  # Allow deletion
        else:
            # Non-superusers cannot delete admin mappings
            if instance.volume_group is None:
                raise PermissionDenied("Cannot delete admin mappings")

            # Volume Group users can only delete their own VG mappings
            if user_context["user_type"] == "volume_group":
                volume_group_id = user_context.get("volume_group_id")
                if instance.volume_group_id != volume_group_id:
                    raise PermissionDenied("Cannot delete mappings from other volume groups")
                if instance.pharmacy is not None:
                    raise PermissionDenied("Cannot delete pharmacy-specific mappings")

            # Pharmacy users can only delete their own pharmacy mappings
            elif user_context["user_type"] == "pharmacy":
                pharmacy_id = user_context.get("pharmacy_id")
                volume_group_id = user_context.get("volume_group_id")

                if instance.volume_group_id != volume_group_id:
                    raise PermissionDenied("Cannot delete mappings from other volume groups")
                if instance.pharmacy_id != pharmacy_id:
                    raise PermissionDenied("Cannot delete mappings from other pharmacies")

        super().perform_destroy(instance)
    
    @action(detail=False, methods=[HTTPMethod.GET])
    def debug_mappings(self, request):
        """
        Debug endpoint to see all mappings with their volume_group and pharmacy values
        """
        user_context = self._get_user_context()

        # Get pharmacy_software filter if provided
        pharmacy_software = request.query_params.get('pharmacy_software')

        if pharmacy_software:
            all_mappings = models.FileDBMapping.objects.filter(pharmacy_software_id=pharmacy_software)
        else:
            all_mappings = models.FileDBMapping.objects.all()

        debug_data = []

        for mapping in all_mappings:
            debug_data.append({
                "id": str(mapping.id),
                "dest_col_name": mapping.dest_col_name,
                "source_col_name": mapping.source_col_name,
                "volume_group_id": str(mapping.volume_group_id) if mapping.volume_group_id else None,
                "pharmacy_id": str(mapping.pharmacy_id) if mapping.pharmacy_id else None,
                "pharmacy_software_id": str(mapping.pharmacy_software_id) if mapping.pharmacy_software_id else None,
                "distributor_id": str(mapping.distributor_id) if mapping.distributor_id else None,
                "created_by": mapping.created_by.username if mapping.created_by else None,
            })

        return Response({
            "user_context": user_context,
            "total_mappings": all_mappings.count(),
            "pharmacy_software_filter": pharmacy_software,
            "mappings": debug_data
        })

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

        Available to:
        - Pharmacy users: Can resubmit their own failed processes
        - Volume group users: Can resubmit failed processes from their volume group
        - Admin/SuperUser: Can resubmit ANY failed process to assist users
        """
        try:
            # Admin users can access any process log, even if not in their filtered queryset
            # This is already handled by get_queryset() but we explicitly note it here
            process_log = self.get_object()
            pharmacy_id = request.data.get("pharmacy")

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

            # Save file to temp location for Celery task
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')

            if is_zip:
                # Take the first ZIP
                zip_file = next(f for f in uploaded_files if f.name.endswith(".zip"))
                temp_file.write(zip_file.read())
                temp_file.close()

                # Trigger Celery task
                process_zip_file_task.delay(
                    temp_file.name,
                    process_log.id,
                    process_log.id,
                    pharmacy_id,
                    True
                )
                return Response(
                    {"message": "Uploaded ZIP accepted. Reprocessing started."},
                    status=status.HTTP_200_OK,
                )

            # Otherwise multiple single files (xlsx/csv)
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in uploaded_files:
                    zf.writestr(f.name, f.read())

            temp_file.write(zip_buffer.getvalue())
            temp_file.close()

            # Trigger Celery task
            process_zip_file_task.delay(
                temp_file.name,
                process_log.id,
                process_log.id,
                pharmacy_id,
                True
            )
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

    @action(detail=True, methods=[HTTPMethod.GET])
    def task_status(self, request, pk):
        """
        Check the Celery task status for a process log.
        Returns the current status of the background task processing.
        """
        from celery.result import AsyncResult
        from django_celery_results.models import TaskResult

        try:
            process_log = models.ProcessLogHdr.objects.get(id=pk)

            # Find the most recent task for this process log
            recent_task = TaskResult.objects.filter(
                task_name="audit.process_zip_file"
            ).order_by("-date_created").first()

            if not recent_task:
                return Response({
                    "status": "NO_TASK",
                    "message": "No background task found for this process",
                    "process_status": process_log.status.description if process_log.status else "Unknown"
                })

            # Get task result details
            task_result = AsyncResult(recent_task.task_id)

            return Response({
                "task_id": recent_task.task_id,
                "status": recent_task.status,  # PENDING, STARTED, SUCCESS, FAILURE, RETRY
                "result": recent_task.result,
                "date_created": recent_task.date_created,
                "date_done": recent_task.date_done,
                "process_status": process_log.status.description if process_log.status else "Unknown",
                "process_log_id": process_log.id
            })

        except models.ProcessLogHdr.DoesNotExist:
            return Response(
                {"error": f"ProcessLog with ID {pk} does not exist"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def get_queryset(self):
            """
            Filter queryset based on user permissions:
            - Pharmacy users: See only their own pharmacy's process logs
            - Volume group users: See all process logs from pharmacies in their volume group
            - Admin/SuperUser: See ALL process logs (no filtering applied)
            """
            queryset = super().get_queryset()
            request_user = self.request.user

            # Check if user is admin/superuser
            is_admin = (
                getattr(request_user, 'is_superuser', False) or
                (hasattr(request_user, 'role') and
                 getattr(request_user.role, 'code', None) == 'SuperUser')
            )

            # Admin/SuperUser - no filtering, return all records immediately
            if is_admin:
                return queryset

            if request_user.pharmacy:
                # Pharmacy user - filter by their pharmacy
                queryset = queryset.filter(
                    process_log_detail_process_log__pharmacy=request_user.pharmacy
                ).distinct()

            elif request_user.volume_group:
                # Volume group user - filter by all pharmacies in their volume group
                pharmacy_ids = list(Pharmacy.objects.filter(
                    volume_group=request_user.volume_group
                ).values_list("id", flat=True))

                if pharmacy_ids:
                    queryset = queryset.filter(
                        process_log_detail_process_log__pharmacy__in=pharmacy_ids
                    ).distinct()

            # For other users without pharmacy/volume_group but not admin, return all
            # (fallback behavior for legacy compatibility)
            return queryset

    @action(detail=True, methods=[HTTPMethod.POST])
    def execute(self, request, **kwargs):
        obj = self.get_object()
        try:
            obj.status = get_processing_status(ProcessingStatusCodes.Inprogress.value)
            obj.save()
            process_audit_data = ProcessAuditData()
            executor.submit(
                process_audit_data.trigger_process,
                obj
            )
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

        # Revoke any running Celery tasks for this process
        from celery import current_app
        from django_celery_results.models import TaskResult

        active_tasks = TaskResult.objects.filter(
            task_name="audit.process_zip_file",
            status__in=["PENDING", "STARTED"]
        ).order_by('-date_created')

        for task in active_tasks:
            try:
                current_app.control.revoke(task.task_id, terminate=True, signal='SIGKILL')
                logger.info(f"Revoked Celery task {task.task_id} for process {instance.id}")
            except Exception as e:
                logger.warning(f"Failed to revoke task {task.task_id}: {e}")

        # Clear Redis cache for this process
        from django.core.cache import cache
        cache_keys = [
            f"process_{instance.id}_*",
            f"pharmacy_{instance.id}",
        ]
        for key in cache_keys:
            try:
                cache.delete(key)
            except Exception as e:
                logger.warning(f"Failed to clear cache key {key}: {e}")

        # Clean up local temp_files and audit_files folders (keep S3 files)
        from .util import remove_dir_recursive
        temp_dir = os.path.join(os.getcwd(), "temp_files", f"process_{instance.id}")
        audit_dir = os.path.join(os.getcwd(), settings.AUDIT_FILES_LOCATION, instance.name)

        remove_dir_recursive(temp_dir)
        remove_dir_recursive(audit_dir)

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

                # <<<< CREATE INITIAL ProcessLogDetail TO MAKE ENTRY VISIBLE IMMEDIATELY >>>>
                # This ensures the process log appears in the audit logs list right away
                pharmacy_id = request.data.get("pharmacy")
                if pharmacy_id:
                    # Check if a ProcessLogDetail already exists for this pharmacy
                    existing_detail = models.ProcessLogDetail.objects.filter(
                        process_log=process_log,
                        pharmacy_id=pharmacy_id
                    ).first()

                    if not existing_detail:
                        # Create placeholder detail to make the log visible immediately
                        models.ProcessLogDetail.objects.create(
                            process_log=process_log,
                            pharmacy_id=pharmacy_id,
                            file_name="Processing...",
                            file_url=""
                        )

            data = request.data
            uploaded_files = request.FILES.getlist("file")

            logger.info(f"Received pharmacy value: {data.get('pharmacy')} (type: {type(data.get('pharmacy'))})")

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

            # Save file to temp location for Celery task
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')

            if is_zip:
                temp_file.write(zip_file.read())
                temp_file.close()

                # Trigger Celery task
                process_zip_file_task.delay(
                    temp_file.name,
                    process_log.id,
                    obj.id,
                    data.get("pharmacy"),
                    is_resubmission
                )
            else:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    for uploaded_file in uploaded_files:
                        zip_file.writestr(uploaded_file.name, uploaded_file.read())

                temp_file.write(zip_buffer.getvalue())
                temp_file.close()

                pharmacy = data.get("pharmacy")
                # Trigger Celery task
                process_zip_file_task.delay(
                    temp_file.name,
                    process_log.id,
                    obj.id,
                    pharmacy,
                    is_resubmission
                )

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
            logger.error(f"automation_process error for pk={pk}: {str(e)}", exc_info=True)
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

    @action(detail=True, methods=[HTTPMethod.POST])
    def generate_report(self, request, pk):
        """
        Generate custom report data with date filters for the reports page.
        Returns JSON data matching the Excel output format.
        """
        try:
            from .constants import get_output_report_sql
            from core.utils import get_sql_alchemy_conn
            import pandas as pd

            obj = self.get_object()

            # Extract filter parameters
            pharmacy_from_date = request.data.get('pharmacy_from_date')
            pharmacy_to_date = request.data.get('pharmacy_to_date')
            distributor_from_date = request.data.get('distributor_from_date')
            distributor_to_date = request.data.get('distributor_to_date')
            group = request.data.get('group')
            pcn = request.data.get('pcn')
            bin_number = request.data.get('bin_number')

            # Get the SQL query
            sql_query = get_output_report_sql(
                process_log_id=obj.id,
                pharmacy_from_date=pharmacy_from_date,
                pharmacy_to_date=pharmacy_to_date,
                distributor_from_date=distributor_from_date,
                distributor_to_date=distributor_to_date,
                group=group,
                pcn=pcn,
                bin_number=bin_number
            )

            # Execute query and get DataFrame
            df = pd.read_sql_query(sql_query, con=get_sql_alchemy_conn())

            if df.empty:
                return Response({
                    'report_data': [],
                    'count': 0,
                    'distributor_columns': [],
                    'filters_applied': {
                        'pharmacy_from_date': pharmacy_from_date,
                        'pharmacy_to_date': pharmacy_to_date,
                        'distributor_from_date': distributor_from_date,
                        'distributor_to_date': distributor_to_date,
                    }
                }, status=status.HTTP_200_OK)

            # Format NDC
            def format_ndc(x):
                if x and str(x) != 'None':
                    x = str(x)
                    if len(x) < 11:
                        x = "0" * (11 - len(x)) + x
                    return x[:5] + "-" + x[5:9] + "-" + x[9:11]
                return x

            df["NDC"] = df["NDC"].astype(str).apply(format_ndc)
            df = df.fillna(0)

            # Aggregate by NDC to avoid duplicate rows (same logic as Excel generation)
            df_agg = df.groupby(
                ["NDC", "Brand", "Drug Name", "Strength", "Pack", "description"],
                as_index=False
            ).agg({
                "Dispense Qty in Packs": "sum",
                "Dispense Qty in Units": "sum",
                "Total Insurance paid": "sum",
                "Patient Co-pay": "sum",
                "No of RX": "sum",
                "distributor_quantity": "sum"
            })

            # Pivot to create distributor columns
            pivot = pd.pivot_table(
                df_agg,
                values="distributor_quantity",
                index=[
                    "NDC", "Brand", "Drug Name", "Strength", "Pack",
                    "Dispense Qty in Packs", "Dispense Qty in Units",
                    "Total Insurance paid", "Patient Co-pay", "No of RX"
                ],
                columns=["description"],
                aggfunc="sum",
                fill_value=0
            )

            # Remove column "0" if it exists
            if 0 in pivot.columns:
                pivot = pivot.drop(0, axis=1)

            # Reset index to make it a regular DataFrame
            pivot = pivot.reset_index()

            # Get distributor column names
            distributor_columns = [col for col in pivot.columns if col not in [
                "NDC", "Brand", "Drug Name", "Strength", "Pack",
                "Dispense Qty in Packs", "Dispense Qty in Units",
                "Total Insurance paid", "Patient Co-pay", "No of RX"
            ]]

            # Calculate Total and Difference
            pivot["Total"] = pivot[distributor_columns].sum(axis=1)
            pivot["Difference"] = pivot["Total"] - pivot["Dispense Qty in Units"]

            # Convert to JSON format
            report_data = []
            for _, row in pivot.iterrows():
                row_data = {
                    'ndc': row['NDC'],
                    'brand': row['Brand'],
                    'drugName': row['Drug Name'],
                    'strength': row['Strength'],
                    'pack': row['Pack'],
                    'dispenseQtyInPacks': float(row['Dispense Qty in Packs']),
                    'dispenseQtyInUnits': float(row['Dispense Qty in Units']),
                    'totalInsurancePaid': float(row['Total Insurance paid']),
                    'patientCoPay': float(row['Patient Co-pay']),
                    'noOfRx': int(row['No of RX']),
                    'total': float(row['Total']),
                    'difference': float(row['Difference']),
                }

                # Add distributor columns dynamically
                for dist_col in distributor_columns:
                    row_data[f'distributor_{dist_col}'] = float(row[dist_col])

                report_data.append(row_data)

            return Response({
                'report_data': report_data,
                'count': len(report_data),
                'distributor_columns': distributor_columns,
                'filters_applied': {
                    'pharmacy_from_date': pharmacy_from_date,
                    'pharmacy_to_date': pharmacy_to_date,
                    'distributor_from_date': distributor_from_date,
                    'distributor_to_date': distributor_to_date,
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"generate_report error for pk={pk}: {str(e)}", exc_info=True)
            return Response(
                {"error": str(e), "message": "Failed to generate report"},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=[HTTPMethod.POST])
    def export_report(self, request, pk):
        """
        Export custom report to Excel with date filters.
        Returns Excel file as binary data for download.
        """
        try:
            from .constants import get_output_report_sql
            from .util import get_sql_alchemy_conn
            import os
            from datetime import datetime
            import tempfile

            obj = self.get_object()

            # Extract filter parameters from request (use originals if not provided)
            pharmacy_from_date = request.data.get('pharmacy_from_date') or obj.pharmacy_from_date
            pharmacy_to_date = request.data.get('pharmacy_to_date') or obj.pharmacy_to_date
            distributor_from_date = request.data.get('distributor_from_date') or obj.distributor_from_date
            distributor_to_date = request.data.get('distributor_to_date') or obj.distributor_to_date

            # Get the data using SQL query
            df = pd.read_sql_query(
                get_output_report_sql(
                    obj.id,
                    pharmacy_from_date,
                    pharmacy_to_date,
                    distributor_from_date,
                    distributor_to_date,
                    obj.group,
                    obj.pcn,
                    obj.bin_number,
                ),
                con=get_sql_alchemy_conn(),
            )

            # Format NDC
            def format_ndc(x):
                if pd.notna(x):
                    x = str(x)
                    if len(x) < 11:
                        x = "0" * (11 - len(x)) + x
                    return x[:5] + "-" + x[5:9] + "-" + x[9:11]
                return x

            df["NDC"] = df["NDC"].astype(str).apply(format_ndc)
            df = df.fillna(0)

            # Aggregate to avoid duplicate rows
            df_agg = df.groupby(
                ["NDC", "Brand", "Drug Name", "Strength", "Pack", "description"],
                as_index=False
            ).agg({
                "Dispense Qty in Packs": "sum",
                "Dispense Qty in Units": "sum",
                "Total Insurance paid": "sum",
                "Patient Co-pay": "sum",
                "No of RX": "sum",
                "distributor_quantity": "sum"
            })

            # Pivot to create distributor columns
            pivot = pd.pivot_table(
                df_agg,
                values="distributor_quantity",
                index=[
                    "NDC", "Brand", "Drug Name", "Strength", "Pack",
                    "Dispense Qty in Packs", "Dispense Qty in Units",
                    "Total Insurance paid", "Patient Co-pay", "No of RX"
                ],
                columns=["description"],
                aggfunc="sum",
                fill_value=0
            )

            # Remove column "0" if it exists
            if 0 in pivot.columns:
                pivot = pivot.drop(0, axis=1)

            pivot = pivot.reset_index()

            # Get distributor column names
            distributor_columns = [col for col in pivot.columns if col not in [
                "NDC", "Brand", "Drug Name", "Strength", "Pack",
                "Dispense Qty in Packs", "Dispense Qty in Units",
                "Total Insurance paid", "Patient Co-pay", "No of RX"
            ]]

            # Calculate Total and Difference
            pivot["Total"] = pivot[distributor_columns].sum(axis=1)
            pivot["Difference"] = pivot["Total"] - pivot["Dispense Qty in Units"]

            # Create Excel file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
            temp_path = temp_file.name
            temp_file.close()

            # Write to Excel
            with pd.ExcelWriter(temp_path, engine="xlsxwriter") as writer:
                pivot.to_excel(writer, sheet_name="Comparison Report", index=False)

            # Read the file
            with open(temp_path, 'rb') as f:
                file_data = f.read()

            # Clean up temp file
            os.remove(temp_path)

            # Generate filename
            date_str = datetime.now().strftime("%Y-%m-%d")
            filename = f"Comparison_Report_{obj.name}_{date_str}.xlsx"

            # Return as file download
            response = HttpResponse(
                file_data,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}"'

            return response

        except Exception as e:
            logger.error(f"export_report error for pk={pk}: {str(e)}", exc_info=True)
            return Response(
                {"error": str(e), "message": "Failed to export report"},
                status=status.HTTP_400_BAD_REQUEST
            )


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
            executor.submit(
                batch_process_files,
                file_location, file_name, file, obj, output_file_name
            )
            return Response({"message": "Process Triggered"}, status=status.HTTP_200_OK)
        except Exception as e:
            return HttpResponseServerError("File cleaning failed due to: " + str(e))


class Errorlogsviewset(CoreViewset):
    serializer_class = serializers.ErrorLogserializer
    queryset = models.ErrorLogs.objects.all()


class ErrorSeverityviewset(CoreViewset):
    serializer_class = serializers.ErrorSeverityserializer
    queryset = models.ErrorSeverity.objects.all()
