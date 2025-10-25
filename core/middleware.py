from django.conf import settings
from rest_framework.authtoken.models import Token
from rest_framework.authentication import get_authorization_header
from datetime import datetime, timedelta
from django.http import JsonResponse
import pytz

class UserAuthenticationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        auth = get_authorization_header(request).split()
        if auth and len(auth) > 1:
            try:
                if "bearer" in str(auth[0].lower()):
                    token = Token.objects.get(key=auth[1].decode())
                    if token.created + timedelta(minutes=settings.AUTH_TOKEN_LIFE) < datetime.now().astimezone(pytz.UTC):
                        token.delete()
                        return JsonResponse({"detail": "Invalid/Expired token"}, status=403)
                    request.user = token.user
            except Exception:
                return JsonResponse({"detail": "Invalid/Expired token"}, status=403)

        return self.get_response(request)


class DisableCSRFMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        setattr(request, "_dont_enforce_csrf_checks", True)
        return self.get_response(request)
