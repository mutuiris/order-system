import jwt
import logging
from datetime import datetime, timedelta
from django.conf import settings
from django.contrib.auth.models import User
from rest_framework import authentication, exceptions
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
        auth_header = authentication.get_authorization_header(request).split()

        if not auth_header or auth_header[0].lower() != b'bearer':
            return None
        
        if len(auth_header) == 1:
            msg = _('Invalid token header. Token string should not contain invalid characters')
            raise exceptions.AuthenticationFailed(msg)

        if len(auth_header) > 2:
            msg = _('Invalid token header. Token string should not contain spaces.')
            raise exceptions.AuthenticationFailed(msg)

        try:
            token = auth_header[1].decode('utf-8')
        except UnicodeError:
            msg = _('Invalid token header. Token string should not contain invalid characters.')
            raise exceptions.AuthenticationFailed(msg)

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
            raise exceptions.AuthenticationFailed(msg)
        except jwt.DecodeError:
            msg = _('Error decoding token')
            raise exceptions.AuthenticationFailed(msg)
        except jwt.InvalidTokenError:
            msg = _('Invalid token')
            raise exceptions.AuthenticationFailed(msg)
        
        try:
            user = User.objects.get(id=payload['user_id'])
        except User.DoesNotExist:
            msg = _('No user matching this token was found')
            raise exceptions.AuthenticationFailed(msg)
        
        if not user.is_active:
            msg = _('This user has been deactivated')
            raise exceptions.AuthenticationFailed(msg)
        
        return (user, token)

    @staticmethod
    def generate_jwt_token(user):
        """
        Generate JWT token for authenticated user
        """
        payload = {
            'user_id': user.id,
            'email': user.email,
            'exp': datetime.utcnow() + timedelta(hours=24),
            'iat': datetime.utcnow(),
        }

        token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
        return token

    @staticmethod
    def get_user_from_token(token):
        """
        Extract user information from JWT token for token validation
        and user information extraction
        """
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            return {
                'user_id': payload.get('user_id'),
                'email': payload.get('email'),
                'exp': payload.get('exp'),
                'iat': payload.get('iat'),
            }
        except (jwt.ExpiredSignatureError, jwt.DecodeError, jwt.InvalidTokenError):
            return None