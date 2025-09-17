import jwt
import logging
from datetime import datetime, timedelta, timezone
from django.conf import settings
from django.contrib.auth.models import User
from rest_framework import authentication
from rest_framework.exceptions import AuthenticationFailed
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


class JWTAuthentication(authentication.BaseAuthentication):
    """
    Custom JWT authentication for API requests
    Validated JWT tokens and returns authenticated user
    """

    authentication_header_prefix = 'Bearer'

    def authenticate(self, request):
        """
        Authenticated the request and return a user, token tuple
        """
        auth_header = request.META.get('HTTP_AUTHORIZATION')

        if not auth_header:
            return None

        auth_header_parts = auth_header.split()

        if len(auth_header_parts) != 2 or auth_header_parts[0] != self.authentication_header_prefix:
            return None

        token = auth_header_parts[1]

        if ' ' in token:
            raise AuthenticationFailed(
                'Token string should not contain spaces')

        if not token:
            raise AuthenticationFailed(
                'Token string should not contain invalid characters')

        return self._authenticate_credentials(token)

    def _authenticate_credentials(self, token):
        """
        Authenticate given credentials and return user
        """
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=['HS256']
            )
        except jwt.ExpiredSignatureError:
            msg = _('Token has expired')
            raise AuthenticationFailed(msg)
        except jwt.InvalidTokenError:
            msg = _('Error decoding token')
            raise AuthenticationFailed(msg)

        try:
            user = User.objects.get(pk=payload['user_id'])
        except User.DoesNotExist:
            msg = _('No user matching this token was found')
            raise AuthenticationFailed(msg)

        if not user.is_active:
            msg = _('This user has been deactivated')
            raise AuthenticationFailed(msg)

        return user, token

    def authenticate_header(self, request):
        """
        Return a string to be used as the value of the `WWW-Authenticate`
        header in a `401 Unauthenticated` response, or `None` if the
        authentication scheme should return `403 Permission Denied` responses.
        """
        return 'Bearer realm="api"'

    @staticmethod
    def generate_jwt_token(user):
        """
        Generate JWT token for authenticated user
        """
        payload = {
            'user_id': user.pk,
            'email': user.email,
            'exp': datetime.now(timezone.utc) + timedelta(hours=24),
            'iat': datetime.now(timezone.utc),
        }

        token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
        return token

    @staticmethod
    def get_user_from_token(token):
        """
        Extract user information from JWT token without authentication
        """
        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=['HS256'])
            return payload
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None


def generate_jwt_token(user):
    """Generate JWT token for authenticated user"""
    return JWTAuthentication.generate_jwt_token(user)
