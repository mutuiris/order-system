"""
Unit tests for Customer serializers
Tests serialization, deserialization, validation, and custom methods
"""

import pytest
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.exceptions import ValidationError

from customers.api.serializers import (AuthCallbackSerializer,
                                       AuthTokenSerializer, CustomerSerializer,
                                       CustomerUpdateSerializer,
                                       UserSerializer)
from customers.models import Customer


class UserSerializerTest(TestCase):
    """Test UserSerializer functionality"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            first_name="John",
            last_name="Doe",
        )

    def test_user_serialization(self):
        """Test serializing user data"""
        serializer = UserSerializer(self.user)
        data = serializer.data

        self.assertEqual(data["id"], self.user.pk)
        self.assertEqual(data["username"], "testuser")
        self.assertEqual(data["email"], "test@example.com")
        self.assertEqual(data["first_name"], "John")
        self.assertEqual(data["last_name"], "Doe")
        self.assertIn("date_joined", data)

    def test_user_read_only_fields(self):
        """Test that read only fields cannot be updated"""
        serializer = UserSerializer(
            self.user,
            data={
                "id": 999,
                "username": "newusername",
                "date_joined": "2023-01-01T00:00:00Z",
                "first_name": "Jane",
            },
        )

        self.assertTrue(serializer.is_valid())
        updated_user = serializer.save()

        # Read only fields should not change
        self.assertEqual(updated_user.pk, self.user.pk)
        self.assertEqual(updated_user.username, "testuser")

        # Editable fields should change
        self.assertEqual(updated_user.first_name, "Jane")

    def test_user_serializer_fields(self):
        """Test all expected fields are present"""
        serializer = UserSerializer(self.user)
        expected_fields = {
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "date_joined",
        }
        self.assertEqual(set(serializer.data.keys()), expected_fields)


class CustomerSerializerTest(TestCase):
    """Test CustomerSerializer functionality"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            first_name="John",
            last_name="Doe",
        )

        self.customer = Customer.objects.create(
            user=self.user, phone_number="+254700123456"
        )

    def test_customer_serialization(self):
        """Test serializing customer data"""
        serializer = CustomerSerializer(self.customer)
        data = serializer.data

        self.assertEqual(data["id"], self.customer.pk)
        self.assertEqual(data["phone_number"], "+254700123456")
        self.assertEqual(data["full_name"], "John Doe")
        self.assertEqual(data["email"], "test@example.com")
        self.assertTrue(data["is_active"])
        self.assertIn("user", data)
        self.assertIn("created_at", data)
        self.assertIn("updated_at", data)

    def test_customer_nested_user_serialization(self):
        """Test nested user data in customer serialization"""
        serializer = CustomerSerializer(self.customer)
        user_data = serializer.data["user"]

        self.assertEqual(user_data["id"], self.user.pk)
        self.assertEqual(user_data["email"], "test@example.com")
        self.assertEqual(user_data["first_name"], "John")
        self.assertEqual(user_data["last_name"], "Doe")

    def test_customer_read_only_fields(self):
        """Test read only fields in customer serializer"""
        serializer = CustomerSerializer(
            self.customer,
            data={
                "id": 999,
                "full_name": "Should Not Change",
                "email": "shouldnotchange@example.com",
                "phone_number": "+254700654321",
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-01T00:00:00Z",
            },
        )

        self.assertTrue(serializer.is_valid())
        updated_customer = serializer.save()

        # Read only fields should not change
        self.assertEqual(updated_customer.pk, self.customer.pk)
        self.assertEqual(updated_customer.full_name, "John Doe")
        self.assertEqual(updated_customer.email, "test@example.com")

        # Editable field should change
        self.assertEqual(updated_customer.phone_number, "+254700654321")

    def test_customer_serializer_fields(self):
        """Test all expected fields are present"""
        serializer = CustomerSerializer(self.customer)
        expected_fields = {
            "id",
            "user",
            "phone_number",
            "full_name",
            "email",
            "is_active",
            "created_at",
            "updated_at",
        }
        self.assertEqual(set(serializer.data.keys()), expected_fields)


class CustomerUpdateSerializerTest(TestCase):
    """Test CustomerUpdateSerializer functionality"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            first_name="John",
            last_name="Doe",
        )

        self.customer = Customer.objects.create(
            user=self.user, phone_number="+254700123456"
        )

    def test_customer_update_serialization(self):
        """Test updating customer and user data"""
        data = {
            "phone_number": "+254700654321",
            "first_name": "Jane",
            "last_name": "Smith",
        }

        serializer = CustomerUpdateSerializer(self.customer, data=data)
        self.assertTrue(serializer.is_valid())
        updated_customer = serializer.save()

        # Check customer field updated
        self.assertEqual(updated_customer.phone_number, "+254700654321")

        # Check user fields updated
        updated_customer.user.refresh_from_db()
        self.assertEqual(updated_customer.user.first_name, "Jane")
        self.assertEqual(updated_customer.user.last_name, "Smith")

    def test_customer_partial_update(self):
        """Test partial update of customer data"""
        data = {"first_name": "Jane"}

        serializer = CustomerUpdateSerializer(self.customer, data=data, partial=True)
        self.assertTrue(serializer.is_valid())
        updated_customer = serializer.save()

        # Only first name should change
        updated_customer.user.refresh_from_db()
        self.assertEqual(updated_customer.user.first_name, "Jane")
        self.assertEqual(updated_customer.user.last_name, "Doe")
        self.assertEqual(updated_customer.phone_number, "+254700123456")

    def test_customer_update_validation(self):
        """Test validation in update serializer"""
        data = {"first_name": "A" * 31, "phone_number": "+254700654321"}

        serializer = CustomerUpdateSerializer(self.customer, data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("first_name", serializer.errors)

    def test_customer_update_serializer_fields(self):
        """Test update serializer has correct fields"""
        serializer = CustomerUpdateSerializer(self.customer)
        expected_fields = {"phone_number", "first_name", "last_name"}
        self.assertEqual(set(serializer.fields.keys()), expected_fields)


class AuthTokenSerializerTest(TestCase):
    """Test AuthTokenSerializer functionality"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            first_name="John",
            last_name="Doe",
        )

        self.customer = Customer.objects.create(
            user=self.user, phone_number="+254700123456"
        )

    def test_auth_token_serialization(self):
        """Test token response serialization"""
        token_data = {
            "access_token": "test-jwt-token",
            "token_type": "Bearer",
            "expires_in": 86400,
            "user": CustomerSerializer(self.customer).data,
        }

        serializer = AuthTokenSerializer(token_data)
        data = serializer.data

        self.assertEqual(data["access_token"], "test-jwt-token")
        self.assertEqual(data["token_type"], "Bearer")
        self.assertEqual(data["expires_in"], 86400)
        self.assertIn("user", data)
        self.assertEqual(data["user"]["id"], self.customer.pk)

    def test_auth_token_default_values(self):
        """Test default values in token serializer"""
        token_data = {
            "access_token": "test-jwt-token",
            "expires_in": 86400,
            "user": CustomerSerializer(self.customer).data,
        }

        serializer = AuthTokenSerializer(token_data)
        data = serializer.data

        self.assertEqual(data["token_type"], "Bearer")

    def test_auth_token_to_representation(self):
        """Test custom to representation method"""
        token_data = {
            "access_token": "test-jwt-token",
            "token_type": "Bearer",
            "expires_in": 86400,
            "user": CustomerSerializer(self.customer).data,
            "extra_field": "should_not_appear",
        }

        serializer = AuthTokenSerializer(token_data)
        data = serializer.data

        expected_fields = {"access_token", "token_type", "expires_in", "user"}
        self.assertEqual(set(data.keys()), expected_fields)


class AuthCallbackSerializerTest(TestCase):
    """Test AuthCallbackSerializer functionality"""

    def test_valid_callback_data(self):
        """Test valid OAuth callback data"""
        data = {"code": "valid-auth-code", "state": "csrf-protection-state"}

        serializer = AuthCallbackSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["code"], "valid-auth-code")
        self.assertEqual(serializer.validated_data["state"], "csrf-protection-state")

    def test_callback_without_state(self):
        """Test callback data without state parameter"""
        data = {"code": "valid-auth-code"}

        serializer = AuthCallbackSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["code"], "valid-auth-code")
        self.assertNotIn("state", serializer.validated_data)

    def test_callback_missing_code(self):
        """Test callback data missing required code"""
        data = {"state": "csrf-protection-state"}

        serializer = AuthCallbackSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("code", serializer.errors)

    def test_callback_empty_code(self):
        """Test callback with empty code value"""
        data = {"code": ""}

        serializer = AuthCallbackSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("code", serializer.errors)

    def test_callback_whitespace_code(self):
        """Test callback with whitespace-only code"""
        data = {"code": "   "}

        serializer = AuthCallbackSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("code", serializer.errors)


@pytest.mark.django_db
class CustomerSerializerPytestTest:
    """Pytest tests for customer serializers"""

    def test_customer_serializer_with_fixture(self, test_customer):
        """Test customer serializer using pytest"""
        serializer = CustomerSerializer(test_customer)
        data = serializer.data

        assert data["id"] == test_customer.id
        assert data["phone_number"] == test_customer.phone_number
        assert data["is_active"] == test_customer.is_active
        assert "user" in data
        assert "created_at" in data

    def test_customer_update_serializer(self, test_customer):
        """Test customer update serializer"""
        data = {
            "phone_number": "+254700999888",
            "first_name": "Updated",
            "last_name": "Name",
        }

        serializer = CustomerUpdateSerializer(test_customer, data=data)
        assert serializer.is_valid()

        updated_customer = serializer.save()
        assert updated_customer.phone_number == "+254700999888"
        assert updated_customer.user.first_name == "Updated"
        assert updated_customer.user.last_name == "Name"
