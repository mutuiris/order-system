"""
Shared pytest fixtures for order system tests
"""

import os

import django
import pytest
from django.conf import settings

if not settings.configured:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "order_system.test_settings")
    django.setup()

from django.contrib.auth.models import User
from django.test import Client
from rest_framework.test import APIClient

from customers.models import Customer
from orders.models import Order, OrderItem
from products.models import Category, Product


@pytest.fixture
def api_client():
    """API client for testing REST endpoints"""
    return APIClient()


@pytest.fixture
def authenticated_client(api_client, test_user):
    """API client authenticated with JWT token"""
    from order_system.authentication import generate_jwt_token

    token = generate_jwt_token(test_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return api_client


@pytest.fixture
def django_client():
    """Django test client"""
    return Client()


@pytest.fixture
def test_user():
    """Create a test user"""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
        first_name="Test",
        last_name="User",
    )


@pytest.fixture
def test_customer(test_user):
    """Create a test customer profile"""
    return Customer.objects.create(user=test_user, phone_number="+254700123456")


@pytest.fixture
def admin_user():
    """Create an admin user"""
    return User.objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="adminpass123",
    )


@pytest.fixture
def root_category():
    """Create a root product category"""
    return Category.objects.create(
        name="Electronics",
        slug="electronics",
        level=0,
    )


@pytest.fixture
def child_category(root_category):
    """Create a child product category"""
    return Category.objects.create(
        name="Smartphones",
        slug="smartphones",
        parent=root_category,
        level=1,
    )


@pytest.fixture
def test_product(child_category):
    """Create a test product"""
    return Product.objects.create(
        name="Test Smartphone",
        description="A smartphone for testing",
        sku="TEST-SMARTPHONE-001",
        price=499.99,
        category=child_category,
        stock_quantity=50,
    )


@pytest.fixture
def multiple_products(child_category):
    """Create multiple test products"""
    products = []
    for i in range(5):
        product = Product.objects.create(
            name=f"Product {i+1}",
            description=f"Test product {i+1}",
            sku=f"PROD-{i+1:03d}",
            price=99.99 + i * 10,
            category=child_category,
            stock_quantity=10 + i,
        )
        products.append(product)
    return products


@pytest.fixture
def test_order(test_customer):
    """Create a test order"""
    return Order.objects.create(
        customer=test_customer,
        delivery_address="123 Test Street, Nairobi",
        delivery_notes="Test delivery notes",
    )


@pytest.fixture
def test_order_with_items(test_order, test_product):
    """Create a test order with items"""
    OrderItem.objects.create(
        order=test_order,
        product=test_product,
        quantity=2,
    )
    test_order.calculate_totals()
    return test_order


@pytest.fixture
def mock_sms_service():
    """Mock SMS service for testing"""
    from unittest.mock import Mock, patch

    mock_service = Mock()
    mock_service.send_sms.return_value = {
        "success": True,
        "message": "SMS sent successfully",
        "sent_to": "+254700123456",
    }

    with patch("order_system.services.sms_service.sms_service", mock_service):
        yield mock_service


@pytest.fixture
def mock_email_service():
    """Mock Email service for testing"""
    from unittest.mock import patch

    with patch("django.core.mail.send_mail") as mock_send_mail:
        yield mock_send_mail


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """Enable database access for all tests"""
    pass


@pytest.fixture
def transactional_db_access(transactional_db):
    """For tests that need transactional testing"""
    pass


@pytest.fixture
def user_factory():
    """Factory for creating users"""

    def create_user(username=None, email=None, **kwargs):
        import uuid

        if not username:
            username = f"user_{uuid.uuid4().hex[:8]}"
        if not email:
            email = f"{username}@example.com"

        return User.objects.create_user(
            username=username, email=email, password="testpass123", **kwargs
        )

    return create_user


@pytest.fixture
def customer_factory(user_factory):
    """Factory for creating customers"""

    def create_customer(user=None, **kwargs):
        if not user:
            user = user_factory()

        defaults = {"phone_number": "+254700123456"}
        defaults.update(kwargs)

        return Customer.objects.create(user=user, **defaults)

    return create_customer


@pytest.fixture
def product_factory():
    """Factory for creating products"""

    def create_product(category=None, **kwargs):
        if not category:
            category = child_category

        import uuid

        defaults = {
            "name": f"Product {uuid.uuid4().hex[:8]}",
            "sku": f"SKU-{uuid.uuid4().hex[:8].upper()}",
            "price": 99.99,
            "stock_quantity": 10,
            "description": "A test product description",
        }
        defaults.update(kwargs)

        return Product.objects.create(category=category, **defaults)

    return create_product
