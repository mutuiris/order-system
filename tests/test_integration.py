"""
Integration tests for order system
"""
import pytest
from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase, TransactionTestCase
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status

from customers.models import Customer
from products.models import Category, Product
from orders.models import Order, OrderItem
from tests.base import BaseAPITestCase


class CompleteOrderWorkflowTest(BaseAPITestCase):
    """Test complete order workflow from creation to notification"""
    
    def setUp(self) -> None:
        """Set up complete workflow test"""
        super().setUp()
        
        # Create product catalog
        self.electronics = Category.objects.create(
            name='Electronics',
            slug='electronics'
        )
        
        self.smartphones = Category.objects.create(
            name='Smartphones', 
            slug='smartphones',
            parent=self.electronics
        )
        
        self.iphone = Product.objects.create(
            name='iPhone 15',
            sku='IPH-15',
            price=Decimal('999.00'),
            category=self.smartphones,
            stock_quantity=10
        )
    
    @patch('orders.tasks.send_order_notifications.delay')
    def test_end_to_end_order_flow(self, mock_notifications) -> None:
        """Test complete order flow"""
        self.authenticate()
        
        # Create order via API
        url = reverse('order-list')
        order_data = {
            'delivery_address': '123 Integration Test Street',
            'delivery_notes': 'End to end test order',
            'items': [
                {'product': self.iphone.pk, 'quantity': 2}
            ]
        }
        
        response = self.client.post(url, order_data, format='json')
        self.assert_response_success(response, status.HTTP_201_CREATED)
        
        # Verify order creation
        order_id = self.get_json_response(response)['id']
        order = Order.objects.get(pk=order_id)
        
        self.assertEqual(order.customer, self.test_customer)
        self.assertEqual(order.status, Order.CONFIRMED)
        self.assertEqual(order.items.count(), 1)
        
        # Verify stock reduction
        self.iphone.refresh_from_db()
        self.assertEqual(self.iphone.stock_quantity, 8)
        
        # Verify calculations
        expected_subtotal = Decimal('1998.00')
        expected_tax = Decimal('319.68')
        expected_total = Decimal('2317.68')
        
        self.assertEqual(order.subtotal, expected_subtotal)
        self.assertEqual(order.tax_amount, expected_tax)
        self.assertEqual(order.total_amount, expected_total)
        
        # Verify notifications were triggered
        mock_notifications.assert_called_once_with(order.pk)
    
    def test_order_cancellation_workflow(self) -> None:
        """Test complete order cancellation workflow"""
        self.authenticate()
        
        # Create order
        order = Order.objects.create(
            customer=self.test_customer,
            delivery_address='Cancel Test Address'
        )
        
        OrderItem.objects.create(
            order=order,
            product=self.iphone,
            quantity=3
        )
        
        # Simulate stock reduction
        self.iphone.reduce_stock(3)
        self.assertEqual(self.iphone.stock_quantity, 7)
        
        # Cancel order via API
        url = reverse('order-cancel', kwargs={'pk': order.pk})
        response = self.client.post(url)
        
        self.assert_response_success(response)
        
        # Verify order cancelled
        order.refresh_from_db()
        self.assertEqual(order.status, Order.CANCELLED)


class CategoryProductOrderIntegrationTest(TestCase):
    """Test integration between categories, products, and orders"""
    
    def setUp(self) -> None:
        """Set up category, product and order integration test"""
        user = User.objects.create_user('integration', 'test@test.com', 'pass')
        self.customer = Customer.objects.create(user=user, phone_number='+254700123456')
        
        # Create hierarchy
        self.electronics = Category.objects.create(name='Electronics', slug='electronics')
        self.phones = Category.objects.create(name='Phones', slug='phones', parent=self.electronics)
        self.smartphones = Category.objects.create(name='Smartphones', slug='smartphones', parent=self.phones)
        
        # Create products at different levels
        self.general_product = Product.objects.create(
            name='General Electronics Item',
            sku='GEN-001',
            price=Decimal('50.00'),
            category=self.electronics,
            stock_quantity=20
        )
        
        self.phone_product = Product.objects.create(
            name='Basic Phone',
            sku='PHONE-001', 
            price=Decimal('100.00'),
            category=self.phones,
            stock_quantity=15
        )
        
        self.smartphone = Product.objects.create(
            name='Smartphone',
            sku='SMART-001',
            price=Decimal('500.00'),
            category=self.smartphones,
            stock_quantity=10
        )
    
    def test_category_average_price_with_orders(self) -> None:
        """Test average price calculation after orders affect stock"""
        # Create orders that will affect stock
        order1 = Order.objects.create(customer=self.customer)
        OrderItem.objects.create(order=order1, product=self.phone_product, quantity=5)

        order2 = Order.objects.create(customer=self.customer)  
        OrderItem.objects.create(order=order2, product=self.smartphone, quantity=2)

        # Calculate average for phones category
        from django.db.models import Avg
        phones_descendants = [self.phones] + self.phones.get_descendants()
        products_in_phones = Product.objects.filter(category__in=phones_descendants)

        average_price = products_in_phones.aggregate(avg=Avg('price'))['avg']

        self.assertEqual(average_price, Decimal('300.00'))
    
    def test_hierarchical_product_ordering(self) -> None:
        """Test ordering products across category hierarchy"""
        # Create orders to test stock impact
        order = Order.objects.create(customer=self.customer)
        
        OrderItem.objects.create(order=order, product=self.general_product, quantity=1)
        OrderItem.objects.create(order=order, product=self.phone_product, quantity=1)
        OrderItem.objects.create(order=order, product=self.smartphone, quantity=1)
        
        order.calculate_totals()
        
        # Verify order contains products from different hierarchy levels
        self.assertEqual(order.items.count(), 3)
        
        # Verify total calculation across hierarchy
        expected_subtotal = Decimal('650.00')
        self.assertEqual(order.subtotal, expected_subtotal)


class AuthenticationOrderIntegrationTest(BaseAPITestCase):
    """Test authentication integration with order operations"""
    
    def setUp(self) -> None:
        """Set up auth order integration test"""
        super().setUp()
        
        category = Category.objects.create(name='Test', slug='test')
        self.product = Product.objects.create(
            name='Auth Test Product',
            sku='AUTH-001',
            price=Decimal('99.99'),
            category=category,
            stock_quantity=5
        )
    
    def test_jwt_authentication_order_access(self) -> None:
        """Test JWT authentication for order operations"""
        # Create order as authenticated user
        self.authenticate()
        
        url = reverse('order-list')
        data = {
            'delivery_address': '123 Auth Test Street',
            'items': [{'product': self.product.pk, 'quantity': 1}]
        }
        
        response = self.client.post(url, data, format='json')
        self.assert_response_success(response, status.HTTP_201_CREATED)
        
        order_id = self.get_json_response(response)['id']

        # Access order detail with same authentication
        detail_url = reverse('order-detail', kwargs={'pk': order_id})
        response = self.client.get(detail_url)
        self.assert_response_success(response)

        # Remove authentication and try again
        self.unauthenticate()
        # Assert client is unauthenticated
        assert not self.client._credentials or 'HTTP_AUTHORIZATION' not in self.client._credentials
        response = self.client.get(detail_url)
        self.assert_response_error(response, status.HTTP_401_UNAUTHORIZED)
    
    def test_customer_isolation_in_orders(self) -> None:
        """Test customers can only access their own orders"""
        # Create order as first customer
        self.authenticate()

        order = Order.objects.create(customer=self.test_customer)
        
        # Create second customer
        other_user, other_customer, other_token = self.create_authenticated_user(
            'other', 'other@test.com'
        )
        
        # Switch authentication to second customer
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {other_token}')
        
        # Try to access first customer's order
        url = reverse('order-detail', kwargs={'pk': order.pk})
        response = self.client.get(url)
        
        self.assert_response_error(response, status.HTTP_404_NOT_FOUND)


class NotificationIntegrationTest(TransactionTestCase):
    """Test notification system integration with orders"""
    
    def setUp(self) -> None:
        """Set up notification integration test"""
        user = User.objects.create_user(
            username='notify',
            email='notify@test.com',
            password='pass',
            first_name='Notify',
            last_name='User'
        )
        
        self.customer = Customer.objects.create(
            user=user,
            phone_number='+254700123456'
        )
        
        category = Category.objects.create(name='Test', slug='test')
        self.product = Product.objects.create(
            name='Notification Product',
            sku='NOTIFY-001',
            price=Decimal('150.00'),
            category=category,
            stock_quantity=10
        )
    
    @patch('order_system.services.sms_service.sms_service')
    @patch('django.core.mail.send_mail')
    def test_order_confirmation_triggers_notifications(self, mock_email, mock_sms) -> None:
        """Test order confirmation triggers both SMS and email"""
        # Mock successful notifications
        mock_sms.send_sms.return_value = {'success': True}
        mock_email.return_value = True
        
        # Create and confirm order
        order = Order.objects.create(customer=self.customer)
        OrderItem.objects.create(order=order, product=self.product, quantity=2)
        order.calculate_totals()

        from orders.tasks import send_order_sms, send_admin_email
        
        # Execute notification tasks
        sms_result = send_order_sms(order.pk)
        email_result = send_admin_email(order.pk)
        
        # Verify notifications were sent
        self.assertTrue(sms_result['success'])
        self.assertTrue(email_result['success'])
        
        # Verify notification content
        mock_sms.send_sms.assert_called_once()
        mock_email.assert_called_once()
        
        # Check SMS content
        sms_args = mock_sms.send_sms.call_args[0]
        self.assertEqual(sms_args[0], '+254700123456')
        self.assertIn(order.order_number, sms_args[1])
        
        # Check email content
        email_kwargs = mock_email.call_args[1]
        self.assertIn(order.order_number, email_kwargs['subject'])
        self.assertIn('Notify User', email_kwargs['message'])


@pytest.mark.django_db
class IntegrationPytestTest:
    """Pytest integration tests"""
    
    def test_complete_product_to_order_flow(self) -> None:
        """Test complete flow from product creation to order"""
        # Create category hierarchy
        electronics = Category.objects.create(name='Electronics', slug='electronics')
        phones = Category.objects.create(name='Phones', slug='phones', parent=electronics)
        
        # Create product
        product = Product.objects.create(
            name='Integration Test Phone',
            sku='INT-001',
            price=Decimal('299.99'),
            category=phones,
            stock_quantity=8
        )
        
        # Create customer
        from customers.tests.factories import create_user_with_customer
        user, customer = create_user_with_customer()
        
        # Create order
        order = Order.objects.create(customer=customer)
        item = OrderItem.objects.create(order=order, product=product, quantity=3)
        
        # Verify complete integration
        assert order.customer == customer
        assert item.product == product
        assert item.product.category == phones
        assert phones.parent == electronics
        
        # Test hierarchy queries work
        electronics_products = Product.objects.filter(
            category__in=[electronics] + electronics.get_descendants()
        )
        assert product in electronics_products
        
        # Test order calculations
        order.calculate_totals()
        expected_subtotal = Decimal('899.97')
        assert order.subtotal == expected_subtotal
    
    @patch('orders.tasks.send_order_notifications.delay')  
    def test_order_confirmation_workflow(self, mock_notifications) -> None:
        """Test order moves through confirmation workflow"""
        from customers.tests.factories import CustomerFactory
        from products.tests.factories import ProductFactory
        
        customer = CustomerFactory()
        product = ProductFactory(stock_quantity=10)
        
        # Create order
        order = Order.objects.create(customer=customer)
        OrderItem.objects.create(order=order, product=product, quantity=2)
        
        # Initial state
        assert order.status == Order.PENDING
        assert order.can_be_cancelled is True
        
        # Mark as confirmed
        order.mark_as_confirmed()
        
        assert order.status == Order.CONFIRMED
        assert order.can_be_cancelled is True
        mock_notifications.assert_called_once_with(order.pk)
        
        # Move to shipped
        order.status = Order.SHIPPED
        order.save()
        
        assert order.can_be_cancelled is False