"""
Integration tests for Customer API endpoints
Tests authentication, CRUD operations, and business workflows
"""

import json
from unittest.mock import Mock, patch

import pytest
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from customers.models import Customer
from tests.base import BaseAPITestCase


class CustomerViewSetTest(BaseAPITestCase):
    """Test CustomerViewSet API endpoints"""

    def test_get_customer_profile_authenticated(self):
        """Test getting customer profile when authenticated"""
        self.authenticate()

        url = reverse("customer-me")
        response = self.client.get(url)

        self.assert_response_success(response)

        data = self.get_json_response(response)
        self.assertEqual(data["id"], self.test_customer.pk)
        self.assertEqual(data["phone_number"], "+254700123456")
        self.assertEqual(data["full_name"], "Test User")
        self.assertEqual(data["email"], "test@example.com")

    def test_get_customer_profile_unauthenticated(self):
        """Test getting customer profile without authentication"""
        url = reverse("customer-me")
        response = self.client.get(url)

        self.assert_response_error(response, status.HTTP_401_UNAUTHORIZED)

    def test_get_customer_profile_no_profile(self):
        """Test getting profile when user has no customer profile"""
        user_no_profile = User.objects.create_user(
            username="noprofile", email="noprofile@example.com", password="testpass123"
        )

        self.authenticate(user_no_profile)

        url = reverse("customer-me")
        response = self.client.get(url)

        self.assert_response_error(response, status.HTTP_404_NOT_FOUND)

        data = self.get_json_response(response)
        self.assertIn("error", data)
        self.assertEqual(data["error"], "Customer profile not found")

    def test_update_customer_profile_put(self):
        """Test updating customer profile with PUT"""
        self.authenticate()

        url = reverse("customer-update-profile")
        data = {
            "phone_number": "+254700999888",
            "first_name": "Updated",
            "last_name": "Name",
        }

        response = self.client.put(url, data, format="json")

        self.assert_response_success(response)

        # Refresh customer from database
        self.test_customer.refresh_from_db()
        self.test_customer.user.refresh_from_db()

        self.assertEqual(self.test_customer.phone_number, "+254700999888")
        self.assertEqual(self.test_customer.user.first_name, "Updated")
        self.assertEqual(self.test_customer.user.last_name, "Name")

        # Check response data
        response_data = self.get_json_response(response)
        self.assertEqual(response_data["phone_number"], "+254700999888")
        self.assertEqual(response_data["full_name"], "Updated Name")

    def test_update_customer_profile_patch(self):
        """Test partial update of customer profile with PATCH"""
        self.authenticate()

        url = reverse("customer-update-profile")
        data = {"first_name": "Partially Updated"}

        response = self.client.patch(url, data, format="json")

        self.assert_response_success(response)

        # Check only first name was updated
        self.test_customer.user.refresh_from_db()
        self.assertEqual(self.test_customer.user.first_name, "Partially Updated")
        self.assertEqual(self.test_customer.user.last_name, "User")

    def test_update_customer_profile_validation_error(self):
        """Test update with invalid data"""
        self.authenticate()

        url = reverse("customer-update-profile")
        data = {"first_name": "A" * 31, "phone_number": "+254700999888"}

        response = self.client.put(url, data, format="json")

        self.assert_response_error(response, status.HTTP_400_BAD_REQUEST)

        response_data = self.get_json_response(response)
        self.assertIn("first_name", response_data)

    def test_update_profile_unauthenticated(self):
        """Test updating profile without authentication"""
        url = reverse("customer-update-profile")
        data = {"first_name": "Should Fail"}

        response = self.client.put(url, data, format="json")

        self.assert_response_error(response, status.HTTP_401_UNAUTHORIZED)

    def test_update_profile_no_customer_profile(self):
        """Test updating when user has no customer profile"""
        user_no_profile = User.objects.create_user(
            username="noprofile", email="noprofile@example.com", password="testpass123"
        )

        self.authenticate(user_no_profile)

        url = reverse("customer-update-profile")
        data = {"first_name": "Should Fail"}

        response = self.client.put(url, data, format="json")

        self.assert_response_error(response, status.HTTP_404_NOT_FOUND)

    def test_customer_queryset_isolation(self):
        """Test that customers can only see their own profile"""
        # Create another customer
        other_user = User.objects.create_user(
            username="otheruser", email="other@example.com", password="testpass123"
        )

        other_customer = Customer.objects.create(
            user=other_user, phone_number="+254700999999"
        )

        # Authenticate as first user
        self.authenticate()

        url = reverse("customer-list")
        response = self.client.get(url)

        self.assert_response_success(response)

        data = self.get_json_response(response)
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["id"], self.test_customer.pk)


class AuthenticationAPITest(BaseAPITestCase):
    """Test authentication API endpoints"""

    def test_auth_login_endpoint(self):
        """Test authentication login endpoint"""
        url = reverse("auth-login")
        response = self.client.get(url)

        self.assert_response_success(response)

        data = self.get_json_response(response)
        self.assertIn("login_url", data)
        self.assertIn("google-oauth2", data["login_url"])
        self.assertIn("state", data)
        self.assertEqual(data["provider"], "google-oauth2")

    def test_auth_callback_missing_code(self):
        """Test OAuth callback without authorization code"""
        url = reverse("auth-callback", kwargs={"backend": "google-oauth2"})
        data = {"state": "test-state"}

        response = self.client.get(url, data)

        self.assert_response_error(response, status.HTTP_400_BAD_REQUEST)

        data = self.get_json_response(response)
        self.assertIn("error", data)
        self.assertIn("Invalid callback parameters", data["error"])

    def test_auth_callback_empty_code(self):
        """Test OAuth callback with empty code"""
        url = reverse("auth-callback", kwargs={"backend": "google-oauth2"})
        data = {"code": "", "state": "test-state"}

        response = self.client.get(url, data)

        self.assert_response_error(response, status.HTTP_400_BAD_REQUEST)

    def test_auth_success_authenticated(self):
        """Test auth success endpoint when user is authenticated"""
        self.authenticate()

        url = reverse("auth-success")
        response = self.client.get(url)

        self.assert_response_success(response)

        data = self.get_json_response(response)
        self.assertTrue(data["success"])
        self.assertIn("auth_data", data)
        self.assertIn("access_token", data["auth_data"])
        self.assertEqual(data["auth_data"]["user"]["id"], self.test_customer.pk)

    def test_auth_success_unauthenticated(self):
        """Test auth success endpoint when user is not authenticated"""
        url = reverse("auth-success")
        response = self.client.get(url)

        self.assert_response_error(response, status.HTTP_401_UNAUTHORIZED)

        data = self.get_json_response(response)
        self.assertIn("error", data)
        self.assertEqual(data["error"], "Authentication required")

    def test_auth_logout(self):
        """Test logout endpoint"""
        self.authenticate()

        url = reverse("auth-logout")
        response = self.client.post(url)

        self.assert_response_success(response)

        data = self.get_json_response(response)
        self.assertTrue(data["success"])
        self.assertEqual(data["message"], "Successfully logged out")

    def test_auth_logout_unauthenticated(self):
        """Test logout endpoint when not authenticated"""
        url = reverse("auth-logout")
        response = self.client.post(url)

        self.assert_response_error(response, status.HTTP_401_UNAUTHORIZED)

    def test_auth_status_with_customer_profile(self):
        """Test auth status endpoint with customer profile"""
        self.authenticate()

        url = reverse("auth-status")
        response = self.client.get(url)

        self.assert_response_success(response)

        data = self.get_json_response(response)
        self.assertTrue(data["authenticated"])
        self.assertIn("user", data)
        self.assertEqual(data["user"]["id"], self.test_customer.pk)

        # Check permissions
        permissions = data["permissions"]
        self.assertTrue(permissions["can_place_orders"])
        self.assertTrue(permissions["can_view_orders"])
        self.assertTrue(permissions["can_update_profile"])

    def test_auth_status_without_customer_profile(self):
        """Test auth status when user has no customer profile"""
        user_no_profile = User.objects.create_user(
            username="noprofile", email="noprofile@example.com", password="testpass123"
        )

        self.authenticate(user_no_profile)

        url = reverse("auth-status")
        response = self.client.get(url)

        self.assert_response_success(response)

        data = self.get_json_response(response)
        self.assertTrue(data["authenticated"])
        self.assertIn("error", data)
        self.assertEqual(data["error"], "Customer profile not found")

        # Check restricted permissions
        permissions = data["permissions"]
        self.assertFalse(permissions["can_place_orders"])
        self.assertFalse(permissions["can_view_orders"])
        self.assertFalse(permissions["can_update_profile"])

    def test_auth_status_unauthenticated(self):
        """Test auth status endpoint when not authenticated"""
        url = reverse("auth-status")
        response = self.client.get(url)

        self.assert_response_error(response, status.HTTP_401_UNAUTHORIZED)


@pytest.mark.django_db
class CustomerAPIPytestTest:
    """Pytest API tests"""

    def test_get_customer_profile(self, authenticated_client, test_customer):
        """Test getting customer profile using pytest"""
        url = reverse("customer-me")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["id"] == test_customer.id
        assert data["phone_number"] == test_customer.phone_number
        assert data["email"] == test_customer.email

    def test_update_customer_profile(self, authenticated_client, test_customer):
        """Test updating customer profile"""
        url = reverse("customer-update-profile")
        data = {
            "phone_number": "+254700111222",
            "first_name": "Updated",
            "last_name": "User",
        }

        response = authenticated_client.put(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK

        # Verify changes
        test_customer.refresh_from_db()
        test_customer.user.refresh_from_db()

        assert test_customer.phone_number == "+254700111222"
        assert test_customer.user.first_name == "Updated"
        assert test_customer.user.last_name == "User"
