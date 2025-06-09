from django.conf import settings
from rest_framework.authtoken.models import Token
from rest_framework.authentication import get_authorization_header
from datetime import datetime, timedelta
import base64
from rest_framework.response import Response
from rest_framework import status
import pytz
from django.http import HttpResponseForbidden


class UserAuthenticationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        auth = get_authorization_header(request).split()
        if auth and len(auth) > 1:
            try:
                if "bearer" in str(auth[0].lower()):
                    token: Token = Token.objects.get(key=auth[1].decode())
                    if token:
                        if token.created + timedelta(
                            minutes=settings.AUTH_TOKEN_LIFE
                        ) < datetime.now().astimezone(pytz.UTC):
                            token.delete()
                            return HttpResponseForbidden({"Invalid/Expired token"})
                        request.user = token.user
                    else:
                        return HttpResponseForbidden({"Invalid/Expired token"})
            except Exception as e:
                return HttpResponseForbidden({"Invalid/Expired token"})

        response = self.get_response(request)

        return response


class DisableCSRFMiddleware(object):

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        setattr(request, "_dont_enforce_csrf_checks", True)
        response = self.get_response(request)
        return response
