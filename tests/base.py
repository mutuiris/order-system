"""
Base test classes and utilities for order system tests
"""
import json
from decimal import Decimal
from django.test import TestCase, TransactionTestCase
from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from rest_framework import status

from customers.models import Customer
from order_system.authentication import generate_jwt_token


class BaseTestCase(TestCase):
    """
    Base test case with setup and utilities
    """
    
    def setUp(self):
        """Set up test data"""
        self.test_user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        
        self.test_customer = Customer.objects.create(
            user=self.test_user,
            phone_number='+254700123456'
        )
    
    def create_user(self, username='testuser2', email='test2@example.com'):
        """Helper to create additional users"""
        return User.objects.create_user(
            username=username,
            email=email,
            password='testpass123'
        )
    
    def assert_decimal_equal(self, first, second, msg=None):
        """Assert that two decimal values are equal"""
        first_decimal = Decimal(str(first))
        second_decimal = Decimal(str(second))
        self.assertEqual(first_decimal, second_decimal, msg)


class BaseAPITestCase(APITestCase):
    """
    Base API test case with authentication setup
    """
    
    def setUp(self):
        """Set up API test data"""
        self.test_user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        
        self.test_customer = Customer.objects.create(
            user=self.test_user,
            phone_number='+254700123456'
        )
        
        # Generate JWT token for authentication
        self.jwt_token = generate_jwt_token(self.test_user)
    
    def authenticate(self, user=None):
        """Authenticate the API client"""
        if user:
            token = generate_jwt_token(user)
        else:
            token = self.jwt_token
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    
    def unauthenticate(self):
        """Remove authentication credentials"""
        self.client.credentials()
    
    def assert_response_success(self, response, expected_status=status.HTTP_200_OK):
        """Assert that response is successful"""
        self.assertEqual(response.status_code, expected_status)
    
    def assert_response_error(self, response, expected_status=status.HTTP_400_BAD_REQUEST):
        """Assert that response contains an error"""
        self.assertEqual(response.status_code, expected_status)
    
    def get_json_response(self, response):
        """Get JSON data from response"""
        return json.loads(response.content.decode('utf-8'))
    
    def create_authenticated_user(self, username='authuser', email='auth@example.com'):
        """Create user and return with JWT token"""
        user = User.objects.create_user(
            username=username,
            email=email,
            password='testpass123'
        )
        
        customer = Customer.objects.create(
            user=user,
            phone_number='+254700987654'
        )
        
        token = generate_jwt_token(user)
        return user, customer, token


class BaseTransactionTestCase(TransactionTestCase):
    """
    Base test case for testing database transactions
    Used for testing Celery tasks and transaction management
    """
    
    def setUp(self):
        """Set up transaction test data"""
        self.test_user = User.objects.create_user(
            username='transactionuser',
            email='transaction@example.com',
            password='testpass123'
        )
        
        self.test_customer = Customer.objects.create(
            user=self.test_user,
            phone_number='+254700123456'
        )


class MockMixin:
    """
    Mixin for common mocking functionality
    """
    
    def mock_sms_service_success(self):
        """Mock SMS service to return success"""
        from unittest.mock import patch, Mock
        
        mock_service = Mock()
        mock_service.send_sms.return_value = {
            'success': True,
            'message': 'SMS sent successfully',
            'sent_to': ['+254700123456']
        }
        
        return patch('order_system.services.sms_service.sms_service', mock_service)
    
    def mock_sms_service_failure(self):
        """Mock SMS service to return failure"""
        from unittest.mock import patch, Mock
        
        mock_service = Mock()
        mock_service.send_sms.return_value = {
            'success': False,
            'error': 'SMS sending failed'
        }
        
        return patch('order_system.services.sms_service.sms_service', mock_service)
    
    def mock_email_service(self, return_value=True):
        """Mock email service"""
        from unittest.mock import patch
        return patch('django.core.mail.send_mail', return_value=return_value)


# Utility functions for tests
def create_test_categories():
    """Create a category hierarchy for testing"""
    from products.models import Category
    
    # Root category
    electronics = Category.objects.create(
        name='Electronics',
        slug='electronics',
        level=0
    )
    
    # Child categories
    smartphones = Category.objects.create(
        name='Smartphones',
        slug='smartphones',
        parent=electronics,
        level=1
    )
    
    laptops = Category.objects.create(
        name='Laptops',
        slug='laptops',
        parent=electronics,
        level=1
    )
    
    return {
        'electronics': electronics,
        'smartphones': smartphones,
        'laptops': laptops
    }


def create_test_products(categories=None):
    """Create standard test products"""
    from products.models import Product
    
    if not categories:
        categories = create_test_categories()
    
    products = []
    
    # Smartphone products
    iphone = Product.objects.create(
        name='iPhone 15',
        description='Latest iPhone model',
        sku='IPH15-001',
        price='999.00',
        category=categories['smartphones'],
        stock_quantity=10
    )
    products.append(iphone)
    
    samsung = Product.objects.create(
        name='Samsung Galaxy S24',
        description='Latest Samsung Galaxy model',
        sku='SGS24-001',
        price='899.00',
        category=categories['smartphones'],
        stock_quantity=15
    )
    products.append(samsung)
    
    # Laptop products
    macbook = Product.objects.create(
        name='MacBook Pro',
        description='Professional laptop from Apple',
        sku='MBP-001',
        price='1999.00',
        category=categories['laptops'],
        stock_quantity=5
    )
    products.append(macbook)
    
    return products