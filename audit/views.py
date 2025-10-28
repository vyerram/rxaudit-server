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
from rest_framework.exceptions import PermissionDenied


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

    def _get_user_context(self):
        """
        Get user context with role type and relevant IDs.
        Returns dict with:
            - user_type: 'superuser', 'volume_group', or 'pharmacy'
            - pharmacy_id: pharmacy UUID if user is pharmacy user
            - volume_group_id: volume group UUID

        Priority: pharmacy > volume_group > superuser
        This ensures users with assigned pharmacy/volume_group are treated by their role,
        even if they have superuser permissions.
        """
        user = self.request.user
        print(f"\n========== _get_user_context ==========")
        print(f"User: {user.username if user.is_authenticated else 'Anonymous'}")
        print(f"is_authenticated: {user.is_authenticated}")
        print(f"is_superuser: {getattr(user, 'is_superuser', None)}")

        # Get pharmacy ID first (highest priority)
        pharmacy_id = getattr(user, "pharmacy_id", None)
        if not pharmacy_id:
            pharmacy = getattr(user, "pharmacy", None)
            pharmacy_id = getattr(pharmacy, "id", None)

        print(f"pharmacy_id: {pharmacy_id}")

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
        print(f"volume_group_id from user: {volume_group_id}")

        if volume_group_id:
            print(f"✓ RESULT: volume_group user with VG={volume_group_id}")
            print("=" * 40)
            return {
                "user_type": "volume_group",
                "pharmacy_id": None,
                "volume_group_id": volume_group_id
            }

        # Only treat as superuser if no pharmacy AND no volume_group assigned
        if self._is_superuser():
            print("✓ RESULT: superuser (no pharmacy/VG assigned)")
            print("=" * 40)
            return {
                "user_type": "superuser",
                "pharmacy_id": None,
                "volume_group_id": None
            }

        # Fallback: regular user with no special permissions
        print("✓ RESULT: fallback to superuser (no permissions)")
        print("=" * 40)
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

        print(f"\n========== get_queryset ==========")
        print(f"User context: {user_context}")
        print(f"Query params: pharmacy_software={pharmacy_software}, distributor={distributor}")

        # SuperUser sees everything - no filtering
        if user_context["user_type"] == "superuser":
            print("✓ SuperUser - No filtering applied")
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
                print(f"✓ Volume Group User - Filter: Admin OR (VG={volume_group_id} AND pharmacy=null)")

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
                print(f"✓ Pharmacy User - Adding filter: pharmacy={pharmacy_id}")

            if volume_group_id:
                # VG-level mappings (not pharmacy-specific)
                filters |= Q(volume_group_id=volume_group_id, pharmacy__isnull=True)
                print(f"✓ Pharmacy User - Adding filter: VG={volume_group_id} AND pharmacy=null")

            queryset = queryset.filter(filters)

        # Apply additional filters
        if pharmacy_software:
            queryset = queryset.filter(pharmacy_software_id=pharmacy_software)
        if distributor:
            queryset = queryset.filter(distributor_id=distributor)

        print(f"Final queryset count: {queryset.count()}")

        # Print the actual SQL query
        from django.db import connection
        print(f"\nSQL Query:\n{queryset.query}\n")

        # Group mappings by their scope for analysis
        admin_mappings = []
        vg_mappings = []
        pharmacy_mappings = []

        for mapping in queryset:
            if mapping.volume_group_id is None and mapping.pharmacy_id is None:
                admin_mappings.append(mapping)
            elif mapping.pharmacy_id is not None:
                pharmacy_mappings.append(mapping)
            else:
                vg_mappings.append(mapping)

        print(f"\nMapping breakdown:")
        print(f"  Admin mappings (VG=null, pharmacy=null): {len(admin_mappings)}")
        print(f"  VG-level mappings (VG=set, pharmacy=null): {len(vg_mappings)}")
        print(f"  Pharmacy mappings (pharmacy=set): {len(pharmacy_mappings)}")

        if pharmacy_mappings:
            print(f"\n⚠️  WARNING: Found {len(pharmacy_mappings)} pharmacy-specific mappings!")
            print("  First 5 pharmacy mappings:")
            for i, mapping in enumerate(pharmacy_mappings[:5], 1):
                print(f"    {i}. id={str(mapping.id)[:8]}..., VG={str(mapping.volume_group_id)[:8]}, pharmacy={str(mapping.pharmacy_id)[:8]}, source={mapping.source_col_name}, dest={mapping.dest_col_name}")

        print("\nFirst 10 mappings overall:")
        for i, mapping in enumerate(queryset[:10], 1):
            print(f"  {i}. id={str(mapping.id)[:8]}..., VG={str(mapping.volume_group_id)[:8] if mapping.volume_group_id else 'NULL'}, pharmacy={str(mapping.pharmacy_id)[:8] if mapping.pharmacy_id else 'NULL'}, source={mapping.source_col_name}, dest={mapping.dest_col_name}")
        print("=" * 40)

        return queryset

    def perform_create(self, serializer):
        """
        Auto-assign volume_group and pharmacy based on user role when creating mappings.
        - SuperUser: volume_group=null, pharmacy=null (admin mapping, visible to all)
        - Volume Group User: volume_group=user's VG, pharmacy=null (shared across VG)
        - Pharmacy User: volume_group=pharmacy's VG, pharmacy=user's pharmacy
        """
        print("\n" + "=" * 60)
        print("========== PERFORM_CREATE CALLED ==========")
        print("=" * 60)

        user_context = self._get_user_context()
        validated = serializer.validated_data
        record_list = validated if isinstance(validated, list) else [validated]

        print(f"User context in perform_create: {user_context}")
        print(f"Number of records to create: {len(record_list) if isinstance(record_list, list) else 1}")

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

            import logging
            logger = logging.getLogger(__name__)

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

                print(f"Creating mapping with user_type={user_context['user_type']}, volume_group_id={payload.get('volume_group_id')}, pharmacy_id={payload.get('pharmacy_id')}, dest_col={payload.get('dest_col_name')}")

                instance = model_cls.objects.create(**payload)
                print(f"✓ Created mapping: id={str(instance.id)[:8]}..., volume_group={str(instance.volume_group_id)[:8] if instance.volume_group_id else 'NULL'}, pharmacy={str(instance.pharmacy_id)[:8] if instance.pharmacy_id else 'NULL'}")
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
