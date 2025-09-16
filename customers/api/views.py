from rest_framework import viewsets, status, permissions
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from django.shortcuts import redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.urls import reverse
from social_django.utils import psa
from social_core.backends.google import GoogleOAuth2
import logging

from ..models import Customer
from .serializers import (
    CustomerSerializer,
    CustomerUpdateSerializer,
    AuthTokenSerializer,
    AuthCallbackSerializer
)
from order_system.authentication import generate_jwt_token

logger = logging.getLogger(__name__)


class CustomerViewSet(viewsets.ModelViewSet):
    """
    ViewSet for customer profile management
    """
    serializer_class = CustomerSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Return only the authenticated user's customer profile"""
        user = self.request.user
        customer_profile = getattr(user, 'customer_profile', None)
        if customer_profile is not None:
            return Customer.objects.filter(id=customer_profile.id)
        return Customer.objects.none()

    def get_serializer_class(self):
        """Use different serializers for different actions"""
        if self.action in ['update', 'partial_update']:
            return CustomerUpdateSerializer
        return CustomerSerializer

    @action(detail=False, methods=['get'])
    def me(self, request):
        """
        Get current user profile information
        """
        if not hasattr(request.user, 'customer_profile'):
            return Response(
                {'error': 'Customer profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = CustomerSerializer(request.user.customer_profile)
        return Response(serializer.data)

    @action(detail=False, methods=['put', 'patch'])
    def update_profile(self, request):
        """
        Update current user profile information
        """
        if not hasattr(request.user, 'customer_profile'):
            return Response(
                {'error': 'Customer profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        customer = request.user.customer_profile
        serializer = CustomerUpdateSerializer(
            customer,
            data=request.data,
            partial=request.method == 'PATCH'
        )

        if serializer.is_valid():
            serializer.save()
            response_serializer = CustomerSerializer(customer)
            return Response(response_serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def auth_login(request):
    """
    Initiate Google OAuth2 login process
    """
    # Build the Google OAuth2 URL
    google_login_url = request.build_absolute_uri(
        reverse('social:begin', args=['google-oauth2']))

    # Add state parameter for security
    import uuid
    state = str(uuid.uuid4())
    request.session['oauth_state'] = state

    return Response({
        'login_url': f"{google_login_url}?state={state}",
        'provider': 'google-oauth2',
        'message': 'Visit the login_url to authenticate with Google',
        'state': state
    })


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
@psa('social:complete')
def auth_callback(request, backend):
    """
    Handle OAuth2 callback from Google with proper validation
    """
    serializer = AuthCallbackSerializer(data=request.GET)

    if not serializer.is_valid():
        return Response(
            {'error': 'Invalid callback parameters', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

    code = serializer.validated_data['code']
    state = serializer.validated_data.get('state')

    # Verify state parameter if provided
    if state:
        session_state = request.session.get('oauth_state')
        if state != session_state:
            return Response(
                {'error': 'Invalid state parameter - possible CSRF attack'},
                status=status.HTTP_400_BAD_REQUEST
            )

    # Complete OAuth authentication
    try:
        user = request.backend.do_auth(code)

        if user is None:
            return Response(
                {'error': 'Authentication failed - invalid authorization code'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Login the user
        login(request, user)

        # Ensure customer profile exists
        customer, created = Customer.objects.get_or_create(
            user=user,
            defaults={'phone_number': '+254700000000'}
        )

        customer_serializer = CustomerSerializer(customer)

        # Generate structured token response
        token_data = {
            'access_token': generate_jwt_token(user),
            'token_type': 'Bearer',
            'expires_in': 86400,
            'user': customer_serializer.data
        }

        token_serializer = AuthTokenSerializer(token_data)

        return Response({
            'success': True,
            'message': 'OAuth authentication successful',
            'auth_data': token_serializer.data,
            'new_user': created
        })

    except Exception as e:
        logger.error(f"OAuth callback error: {str(e)}")
        return Response(
            {'error': f'Authentication failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def auth_success(request):
    """
    Handle successful authentication
    """
    if request.user.is_authenticated:
        try:
            # Ensure customer profile exists
            customer, created = Customer.objects.get_or_create(
                user=request.user,
                defaults={'phone_number': '+254700000000'}
            )

            # Generate JWT token
            token = generate_jwt_token(request.user)

            customer_serializer = CustomerSerializer(customer)
            token_data = {
                'access_token': token,
                'token_type': 'Bearer',
                'expires_in': 86400,
                'user': customer_serializer.data
            }

            serializer = AuthTokenSerializer(token_data)

            return Response({
                'success': True,
                'message': 'Authentication successful',
                'auth_data': serializer.data
            })

        except Exception as e:
            logger.error(f"Auth success error: {str(e)}")
            return Response(
                {'error': 'Token generation failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    return Response(
        {'error': 'Authentication required'},
        status=status.HTTP_401_UNAUTHORIZED
    )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def auth_logout(request):
    """
    Logout current user
    """
    try:
        logout(request)
        return Response({
            'success': True,
            'message': 'Successfully logged out'
        })
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        return Response(
            {'error': 'Logout failed'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def auth_status(request):
    """
    Check authentication status
    """
    if hasattr(request.user, 'customer_profile'):
        customer_data = CustomerSerializer(request.user.customer_profile).data
        return Response({
            'authenticated': True,
            'user': customer_data,
            'permissions': {
                'can_place_orders': True,
                'can_view_orders': True,
                'can_update_profile': True
            }
        })

    return Response({
        'authenticated': True,
        'user': {
            'id': request.user.id,
            'email': request.user.email,
            'name': request.user.get_full_name()
        },
        'error': 'Customer profile not found',
        'permissions': {
            'can_place_orders': False,
            'can_view_orders': False,
            'can_update_profile': False
        }
    })
