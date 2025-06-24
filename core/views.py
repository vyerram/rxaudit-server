from http import HTTPMethod

from django.db import IntegrityError
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.authtoken.models import Token
from rest_framework.filters import OrderingFilter
import re
from django.contrib.auth import authenticate
from django.apps import apps
from django.db.models import Q
from django.http import JsonResponse
from .constants import TableTypes, only_alphabets_regular_expression
from core.permissions import CheckFunctionalAccess
from rest_framework.pagination import LimitOffsetPagination
from . import models, serializers
from users.serializers import Userserializer
from .logger import logger
from django.middleware.csrf import get_token
from .utils import AllFieldsDjangoFilterBackend, get_foreign_key_rel_dict
from django.core.cache import cache
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.hashers import make_password
from django.core.mail import send_mail
import random
import json
from users.models import User
from django.conf import settings


@csrf_exempt
@api_view([HTTPMethod.POST])
@permission_classes([AllowAny])
def login(request):
    if request.user.is_authenticated:
        token, created = Token.objects.get_or_create(user=request.user)
        user_obj = Userserializer(request.user, many=False)
        return Response(
            status=status.HTTP_200_OK,
            data={
                "token": token.key,
                "message": "Successfull login",
                "user": user_obj.data,
            },
        )
    else:
        username = request.data["username"]
        password = request.data["password"]
        user = authenticate(request, username=username, password=password)
        if user is not None:
            token, created = Token.objects.get_or_create(user=user)
            user_obj = Userserializer(user, many=False)
            get_token(request)
            return Response(
                status=status.HTTP_200_OK,
                data={
                    "token": token.key,
                    "django_csrf_token": request.META["CSRF_COOKIE"],
                    "message": "Successfull login",
                    "user": user_obj.data,
                },
            )
    logger().warn("Unauthorized login")
    return Response(
        status=status.HTTP_401_UNAUTHORIZED, data={"error": "Invalid credentials"}
    )


@permission_classes([IsAuthenticated])
@api_view([HTTPMethod.GET])
def get_retrieve_api_data(self):
    # UI Filter
    # Report ID also as an input ??
    filters = {"user__username": "test_user"}
    # Report Configuration -- Need to remove once implementation is done.
    retrieval_entities = ["TimeTrack", "User", "UserRole", "Customer", "Project"]
    result_list = None
    relation_map = ["user__"]
    # result_list = ["project__pname", "customer__cname", "user__email", "date", "hours"]
    # Logic
    main_entity = retrieval_entities[0]
    main_entity_app_name = models.Tablename.objects.get(name=main_entity)
    first_model = apps.get_model(app_label=main_entity_app_name, model_name=main_entity)
    relations = get_foreign_key_rel_dict(first_model._meta.concrete_fields)
    # Filter logic
    Qr = None
    for key, val in filters.items():
        q = Q(**{"%s__contains" % key: val})
        if Qr:
            Qr = Qr | q  # or & for filtering
        else:
            Qr = q

    queryset = first_model.objects.filter(Qr)
    # Relation logic
    for entity in retrieval_entities:
        if entity in relations.keys():
            queryset = queryset.select_related(relations[entity])
        else:
            queryset = queryset.prefetch_related(relations[entity])
    # Only get required fields
    if result_list:
        queryset = queryset.values(*result_list)
    return JsonResponse(list(queryset), safe=False)


class CoreFilterBackend(AllFieldsDjangoFilterBackend):
    def filter_queryset(self, request, queryset, view):
        if (
            view.action == "list"
            and view.serializer_class.Meta.model._meta.db_table.__contains__(
                TableTypes.LookupTable.value
            )
        ):
            key = re.sub(only_alphabets_regular_expression, "", str(queryset.query))
            if cache.has_key(key):
                return cache.get(key)
        return super().filter_queryset(request, queryset, view)


class Retieve_List_Methods:
    def retrieve(self, request, *args, **kwargs):
        try:
            # Retrieve event begin Logic
            data = super().retrieve(request, *args, **kwargs)
            # Retrieve event end Logic
            return data
        except Exception as e:
            logger().error(e)

    def list(self, request, *args, **kwargs):
        try:
            # Need to implement pagination
            data = super().list(request, *args, **kwargs)
            return data
        except Exception as e:
            logger().error(e)


class CoreReadonlyViewset(ReadOnlyModelViewSet, Retieve_List_Methods):

    permission_classes = [CheckFunctionalAccess]
    # authentication_classes = [SessionAuthentication, BasicAuthentication]
    filter_backends = [CoreFilterBackend, OrderingFilter]
    filter_fields = "__all__"
    ordering_fields = "__all__"


class CoreViewset(
    Retieve_List_Methods,
    ModelViewSet,
    ListAPIView,
):
    permission_classes = [CheckFunctionalAccess]
    # authentication_classes = [SessionAuthentication, BasicAuthentication]
    pagination_class = LimitOffsetPagination
    filter_backends = [CoreFilterBackend, OrderingFilter]
    filter_fields = "__all__"
    ordering_fields = "__all__"

    def create(self, request, *args, **kwargs):
        try:
            bulk = isinstance(request.data, list)

            if not bulk:
                serializer = self.get_serializer(data=request.data, many=False)
            else:
                serializer = self.get_serializer(data=request.data, many=True)
            serializer.is_valid(raise_exception=True)
            super().perform_create(serializer)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except IntegrityError:
            return Response(
                status=status.HTTP_409_CONFLICT, data="DuplicateRecord exists"
            )

    def perform_create(self, serializer):
        try:
            # Create event begin Logic
            super().perform_create(serializer)
            # Create event end Logic
        except Exception as e:
            logger().error(e)

    def perform_update(self, serializer):
        try:
            # Update event begin Logic
            super().perform_update(serializer)
            # Update event end Logic
        except Exception as e:
            logger().error(e)

    def perform_destroy(self, instance):
        try:
            # Delete event begin Logic
            data = super().perform_destroy(instance)
            # Delete event end Logic
        except Exception as e:
            logger().error(e)


class Tablenameviewset(CoreViewset):
    serializer_class = serializers.Tablenameserializer
    queryset = (
        models.Tablename.objects.select_related("Tabletype", "Tablegroup")
        .prefetch_related("Tablerelationship")
        .all()
    )


class Tableattributeviewset(CoreViewset):
    serializer_class = serializers.Tableattributeserializer
    queryset = (
        models.Tableattribute.objects.select_related("Attributetype")
        .prefetch_related("Tablerelationship")
        .all()
    )


class Tablegroupviewset(CoreViewset):
    serializer_class = serializers.Tablegroupserializer
    queryset = models.Tablegroup.objects.prefetch_related("Tablename").all()


class Tablerelationshipviewset(CoreViewset):
    serializer_class = serializers.Tablerelationshipserializer
    queryset = models.Tablerelationship.objects.select_related(
        "Tablename", "Tableattribute", "Keytype"
    ).all()


class Tabletypeviewset(CoreViewset):
    serializer_class = serializers.Tabletypeserializer
    queryset = models.Tabletype.objects.prefetch_related("Tablename").all()


class Attributetypeviewset(CoreViewset):
    serializer_class = serializers.Attributetypeserializer
    queryset = models.Attributetype.objects.all()


class Keytypeviewset(CoreViewset):
    serializer_class = serializers.Keytypeserializer
    queryset = models.Keytype.objects.all()


@api_view([HTTPMethod.POST])
def request_otp(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            email = data.get("email")

            otp = random.randint(1000, 9999)

            user = User.objects.get(email=email)
            user.otp = otp
            user.save()
            nl = "\n"
            subject = "Your Forgot Password OTP Code"
            message = f"""Hi {user.username},{nl}You are receiving this email because we received a password reset request for your account. {nl}{nl}This is your OTP: {otp}{nl}{nl}If you did not request a password reset, no further action is required.{nl}{nl}Regards,{nl}AllwinRx."""
            email_from = settings.EMAIL_HOST_USER
            recipient_list = [email]
            send_mail(subject, message, email_from, recipient_list)

            return JsonResponse({"status": "success"}, status=200)
        except json.JSONDecodeError:
            return JsonResponse(
                {"status": "error", "message": "Invalid JSON"}, status=400
            )
        except User.DoesNotExist:
            return JsonResponse(
                {"status": "error", "message": "User not found"}, status=404
            )
    else:
        return JsonResponse(
            {"status": "error", "message": "Invalid request method"}, status=405
        )


@api_view([HTTPMethod.POST])
def verify_otp(request):
    if request.method == "POST":
        data = json.loads(request.body)
        email = data.get("email")
        otp = data.get("otp")

        try:
            user = User.objects.get(email=email)
            if str(user.otp) == str(otp):
                return JsonResponse({"status": "success"}, status=200)
            else:
                return JsonResponse(
                    {"status": "error", "message": "Invalid OTP"}, status=400
                )
        except User.DoesNotExist:
            return JsonResponse(
                {"status": "error", "message": "User not found"}, status=404
            )


@api_view([HTTPMethod.POST])
def reset_password(request):
    if request.method == "POST":
        data = json.loads(request.body)
        email = data.get("email")
        new_password = data.get("password")

        try:
            user = User.objects.get(email=email)
            user.password = make_password(new_password)
            user.save()
            return JsonResponse({"status": "success"}, status=200)
        except User.DoesNotExist:
            return JsonResponse(
                {"status": "error", "message": "User not found"}, status=404
            )


@api_view([HTTPMethod.POST])
def mfa_request_otp(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            username = data.get("username")

            otp = random.randint(1000, 9999)

            user = User.objects.get(username=username)
            user.otp = otp
            user.save()
            nl = "\n"
            subject = "Your Security Access Code"
            message = f"Hi {user.username},{nl}{nl}The Security code to verify your account is: {otp}{nl}{nl}This message was generated in response to an attempt to access your account. If you did not attempt a login, we recommend change your password immediately.{nl}{nl}Please contact your support team for help!.{nl}{nl}Thanks,{nl}Allwinrx."
            email_from = settings.EMAIL_HOST_USER
            recipient_list = [user.email]
            send_mail(subject, message, email_from, recipient_list)

            return JsonResponse({"status": "success"}, status=200)
        except json.JSONDecodeError:
            return JsonResponse(
                {"status": "error", "message": "Invalid JSON"}, status=400
            )
        except User.DoesNotExist:
            return JsonResponse(
                {"status": "error", "message": "User not found"}, status=404
            )
    else:
        return JsonResponse(
            {"status": "error", "message": "Invalid request method"}, status=405
        )


@csrf_exempt
@api_view([HTTPMethod.POST])
def mfa_verify_otp(request):
    if request.method == "POST":
        data = json.loads(request.body)
        username = data.get("username")
        otp = data.get("otp")

        try:
            user = User.objects.get(username=username)
            if str(user.otp) == str(otp):
                return JsonResponse({"status": "success"}, status=200)
            else:
                return JsonResponse(
                    {"status": "error", "message": "Invalid OTP"}, status=400
                )
        except User.DoesNotExist:
            return JsonResponse(
                {"status": "error", "message": "User not found"}, status=404
            )
