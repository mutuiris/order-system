"""
Tests for authentication system including JWT and OAuth flows
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
from unittest.mock import Mock, patch

import jwt
import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APITestCase

from customers.models import Customer
from order_system.auth_pipeline import create_customer_profile
from order_system.authentication import JWTAuthentication, generate_jwt_token


class JWTAuthenticationTest(TestCase):
    """Test JWT authentication functionality"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

        self.auth = JWTAuthentication()

    def test_generate_jwt_token(self):
        """Test JWT token generation"""
        token = generate_jwt_token(self.user)

        self.assertIsInstance(token, str)
        self.assertTrue(len(token) > 0)

        # Decode and verify token content
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])

        self.assertEqual(payload["user_id"], self.user.pk)
        self.assertEqual(payload["email"], self.user.email)
        self.assertIn("exp", payload)
        self.assertIn("iat", payload)

    def test_jwt_token_expiration(self):
        """Test JWT token expiration time"""
        token = generate_jwt_token(self.user)
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])

        exp_time = datetime.fromtimestamp(payload["exp"], timezone.utc)
        iat_time = datetime.fromtimestamp(payload["iat"], timezone.utc)

        expected_duration = timedelta(hours=24)
        actual_duration = exp_time - iat_time

        self.assertLess(abs(actual_duration - expected_duration).total_seconds(), 60)

    def test_jwt_authentication_valid_token(self):
        """Test authentication with valid JWT token"""
        token = generate_jwt_token(self.user)

        # Create mock request with Bearer token
        mock_request = Mock()
        mock_request.META = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

        auth_result = self.auth.authenticate(mock_request)
        self.assertIsNotNone(auth_result)

        if auth_result is not None:
            user, auth_token = auth_result
            self.assertEqual(user, self.user)
            self.assertEqual(auth_token, token)
        else:
            self.fail("Authentication should have succeeded")

    def test_jwt_authentication_no_header(self):
        """Test authentication without Authorization header"""
        mock_request = Mock()
        mock_request.META = {}

        result = self.auth.authenticate(mock_request)

        self.assertIsNone(result)

    def test_jwt_authentication_invalid_header_format(self):
        """Test authentication with invalid header format"""
        mock_request = Mock()
        mock_request.META = {"HTTP_AUTHORIZATION": "InvalidFormat token"}

        result = self.auth.authenticate(mock_request)

        self.assertIsNone(result)

    def test_jwt_authentication_no_token(self):
        """Test authentication with Bearer but no token"""
        mock_request = Mock()
        mock_request.META = {"HTTP_AUTHORIZATION": "Bearer"}

        with self.assertRaises(AuthenticationFailed) as context:
            self.auth.authenticate(mock_request)

        self.assertIn(
            "Token string should not contain invalid characters", str(context.exception)
        )

    def test_jwt_authentication_multiple_tokens(self):
        """Test authentication with multiple tokens in header"""
        mock_request = Mock()
        mock_request.META = {"HTTP_AUTHORIZATION": "Bearer token1 token2"}

        with self.assertRaises(AuthenticationFailed) as context:
            self.auth.authenticate(mock_request)

        self.assertIn("Token string should not contain spaces", str(context.exception))

    def test_jwt_authentication_expired_token(self):
        """Test authentication with expired token"""
        expired_payload = {
            "user_id": self.user.pk,
            "email": self.user.email,
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "iat": datetime.now(timezone.utc) - timedelta(hours=25),
        }

        expired_token = jwt.encode(
            expired_payload, settings.SECRET_KEY, algorithm="HS256"
        )

        mock_request = Mock()
        mock_request.META = {"HTTP_AUTHORIZATION": f"Bearer {expired_token}"}

        with self.assertRaises(AuthenticationFailed) as context:
            self.auth.authenticate(mock_request)

        self.assertIn("Token has expired", str(context.exception))

    def test_jwt_authentication_invalid_token(self):
        """Test authentication with invalid token signature"""
        invalid_token = "invalid.token.signature"

        mock_request = Mock()
        mock_request.META = {"HTTP_AUTHORIZATION": f"Bearer {invalid_token}"}

        with self.assertRaises(AuthenticationFailed) as context:
            self.auth.authenticate(mock_request)

        self.assertIn("Error decoding token", str(context.exception))

    def test_jwt_authentication_nonexistent_user(self):
        """Test authentication with token for non existent user"""
        payload = {
            "user_id": 99999,
            "email": "nonexistent@example.com",
            "exp": datetime.now(timezone.utc) + timedelta(hours=24),
            "iat": datetime.now(timezone.utc),
        }

        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

        mock_request = Mock()
        mock_request.META = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

        with self.assertRaises(AuthenticationFailed) as context:
            self.auth.authenticate(mock_request)

        self.assertIn("No user matching this token was found", str(context.exception))

    def test_jwt_authentication_inactive_user(self):
        """Test authentication with token for inactive user"""
        # Make user inactive
        self.user.is_active = False
        self.user.save()

        token = generate_jwt_token(self.user)

        mock_request = Mock()
        mock_request.META = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

        with self.assertRaises(AuthenticationFailed) as context:
            self.auth.authenticate(mock_request)

        self.assertIn("This user has been deactivated", str(context.exception))

    def test_get_user_from_token_valid(self):
        """Test extracting user info from valid token"""
        token = generate_jwt_token(self.user)

        user_info = JWTAuthentication.get_user_from_token(token)

        self.assertIsNotNone(user_info)
        if user_info is not None:
            self.assertEqual(user_info["user_id"], self.user.pk)
            self.assertEqual(user_info["email"], self.user.email)
            self.assertIn("exp", user_info)
            self.assertIn("iat", user_info)
        else:
            self.fail("Token parsing should have succeeded")

    def test_get_user_from_token_invalid(self):
        """Test extracting user info from invalid token"""
        invalid_token = "invalid.token.signature"

        user_info = JWTAuthentication.get_user_from_token(invalid_token)

        self.assertIsNone(user_info)


class OAuthPipelineTest(TestCase):
    """Test OAuth authentication pipeline"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username="oauthuser", email="oauth@example.com", password="testpass123"
        )

    def test_create_customer_profile_new_user(self):
        """Test creating customer profile for new OAuth user"""
        # Ensure user has no customer profile
        self.assertFalse(hasattr(self.user, "customer_profile"))

        # Mock strategy and details
        strategy = Mock()
        details = {"phone_number": "+254700123456"}

        result = create_customer_profile(
            strategy=strategy, details=details, user=self.user
        )

        self.assertEqual(result["user"], self.user)

        # Check customer profile was created
        self.user.refresh_from_db()
        self.assertTrue(hasattr(self.user, "customer_profile"))

        customer_profile = getattr(self.user, "customer_profile", None)
        self.assertIsNotNone(customer_profile)
        if customer_profile is not None:
            self.assertEqual(customer_profile.phone_number, "+254700123456")
        else:
            self.fail("Customer profile should have been created")

    def test_create_customer_profile_existing_profile(self):
        """Test pipeline with user who already has customer profile"""
        # Create existing customer profile
        Customer.objects.create(user=self.user, phone_number="+254700999888")

        strategy = Mock()
        details = {"phone_number": "+254700123456"}

        result = create_customer_profile(
            strategy=strategy, details=details, user=self.user
        )

        self.assertEqual(result["user"], self.user)

        # Check customer profile was not duplicated
        customer_count = Customer.objects.filter(user=self.user).count()
        self.assertEqual(customer_count, 1)
        self.user.refresh_from_db()

        customer_profile = getattr(self.user, "customer_profile", None)
        self.assertIsNotNone(customer_profile)
        if customer_profile is not None:
            self.assertEqual(customer_profile.phone_number, "+254700999888")
        else:
            self.fail("Customer profile should exist")

    def test_create_customer_profile_no_phone_in_details(self):
        """Test creating profile when no phone number in OAuth details"""
        strategy = Mock()
        details = {}

        result = create_customer_profile(
            strategy=strategy, details=details, user=self.user
        )

        self.assertEqual(result["user"], self.user)
        self.user.refresh_from_db()
        self.assertTrue(hasattr(self.user, "customer_profile"))

        customer_profile = getattr(self.user, "customer_profile", None)
        self.assertIsNotNone(customer_profile)
        if customer_profile is not None:
            self.assertEqual(customer_profile.phone_number, "+254700000000")
        else:
            self.fail("Customer profile should have been created")

    def test_create_customer_profile_no_user(self):
        """Test pipeline when no user is provided"""
        strategy = Mock()
        details = {"phone_number": "+254700123456"}

        result = create_customer_profile(strategy=strategy, details=details, user=None)

        self.assertEqual(result["user"], None)

    @patch("customers.models.Customer.objects.get_or_create")
    def test_create_customer_profile_database_error(self, mock_get_or_create):
        """Test handling database errors in pipeline"""
        # Mock database error
        mock_get_or_create.side_effect = Exception("Database error")

        strategy = Mock()
        details = {"phone_number": "+254700123456"}

        result = create_customer_profile(
            strategy=strategy, details=details, user=self.user
        )

        self.assertEqual(result["user"], self.user)


class AuthenticationIntegrationTest(APITestCase):
    """Integration tests for authentication workflows"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username="integrationuser",
            email="integration@example.com",
            password="testpass123",
        )

        self.customer = Customer.objects.create(
            user=self.user, phone_number="+254700123456"
        )

    def test_api_authentication_with_jwt(self):
        """Test API access with JWT token"""
        # Generate token
        token = generate_jwt_token(self.user)

        # Make authenticated request
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        from django.urls import reverse

        url = reverse("customer-me")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()

        customer_id = getattr(self.customer, "id", None)
        self.assertIsNotNone(customer_id)
        if customer_id is not None:
            self.assertEqual(data["id"], customer_id)
        else:
            self.fail("Customer should have an ID")

        self.assertEqual(data["email"], self.user.email)

    def test_api_authentication_without_token(self):
        """Test API access without authentication"""
        from django.urls import reverse

        url = reverse("customer-me")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_api_authentication_with_invalid_token(self):
        """Test API access with invalid token"""
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid-token")

        from django.urls import reverse

        url = reverse("customer-me")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@pytest.mark.django_db
class AuthenticationPytestTest:
    """Pytest authentication tests"""

    def test_jwt_token_generation(self, test_user):
        """Test JWT token generation with pytest"""
        token = generate_jwt_token(test_user)

        assert isinstance(token, str)
        assert len(token) > 0

        # Verify token content
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        assert payload["user_id"] == test_user.id
        assert payload["email"] == test_user.email

    def test_jwt_authentication_flow(self, api_client, test_user, test_customer):
        """Test complete JWT authentication flow"""
        # Generate token
        token = generate_jwt_token(test_user)

        # Authenticate client
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        # Make authenticated request
        from django.urls import reverse

        url = reverse("customer-me")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["id"] == test_customer.id
        assert data["email"] == test_user.email
