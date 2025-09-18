"""
Tests for Orders API
"""
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status

from customers.models import Customer
from orders.models import Order, OrderItem
from products.models import Category, Product
from tests.base import BaseAPITestCase


class OrderCreationAPITest(BaseAPITestCase):
    """Test order creation"""
    
    def setUp(self) -> None:
        """Set up test data"""
        super().setUp()
        
        # Create products for ordering
        category = Category.objects.create(name='Electronics', slug='electronics')
        
        self.product1 = Product.objects.create(
            name='iPhone 15',
            sku='IPH-15',
            price=Decimal('999.00'),
            category=category,
            stock_quantity=10
        )
        
        self.product2 = Product.objects.create(
            name='MacBook Pro',
            sku='MBP-001',
            price=Decimal('1999.00'),
            category=category,
            stock_quantity=5
        )
    
    def test_create_order_success(self) -> None:
        """Test successful order creation with stock reduction"""
        self.authenticate()
        
        url = reverse('order-list')
        data = {
            'delivery_address': '123 Test Street, Nairobi',
            'delivery_notes': 'Test delivery notes',
            'items': [
                {'product': self.product1.pk, 'quantity': 2},
                {'product': self.product2.pk, 'quantity': 1}
            ]
        }
        
        response = self.client.post(url, data, format='json')
        self.assert_response_success(response, status.HTTP_201_CREATED)
        
        # Verify order was created
        self.assertEqual(Order.objects.count(), 1)
        order = Order.objects.first()
        assert order is not None
        
        # Verify order details
        self.assertEqual(order.customer, self.test_customer)
        self.assertEqual(order.delivery_address, '123 Test Street, Nairobi')
        self.assertEqual(order.items.count(), 2)
        
        # Verify stock was reduced
        self.product1.refresh_from_db()
        self.product2.refresh_from_db()
        self.assertEqual(self.product1.stock_quantity, 8)
        self.assertEqual(self.product2.stock_quantity, 4)
        
        # Verify order totals
        expected_subtotal = Decimal('3997.00')
        expected_tax = Decimal('639.52')
        expected_total = Decimal('4636.52')
        
        self.assertEqual(order.subtotal, expected_subtotal)
        self.assertEqual(order.tax_amount, expected_tax)
        self.assertEqual(order.total_amount, expected_total)
    
    def test_create_order_insufficient_stock(self) -> None:
        """Test order creation fails with insufficient stock"""
        self.authenticate()
        
        url = reverse('order-list')
        data = {
            'delivery_address': '123 Test Street',
            'items': [
                {'product': self.product1.pk, 'quantity': 15}
            ]
        }
        
        response = self.client.post(url, data, format='json')
        self.assert_response_error(response, status.HTTP_400_BAD_REQUEST)
        
        # Verify no order was created
        self.assertEqual(Order.objects.count(), 0)
        
        # Verify stock unchanged
        self.product1.refresh_from_db()
        self.assertEqual(self.product1.stock_quantity, 10)
    
    def test_create_order_inactive_product(self) -> None:
        """Test order creation fails with inactive product"""
        self.authenticate()
        
        self.product1.is_active = False
        self.product1.save()
        
        url = reverse('order-list')
        data = {
            'delivery_address': '123 Test Street',
            'items': [
                {'product': self.product1.pk, 'quantity': 1}
            ]
        }
        
        response = self.client.post(url, data, format='json')
        self.assert_response_error(response, status.HTTP_400_BAD_REQUEST)
        
        # Verify no order was created
        self.assertEqual(Order.objects.count(), 0)
    
    def test_create_order_requires_authentication(self) -> None:
        """Test order creation requires authentication"""
        url = reverse('order-list')
        data = {
            'delivery_address': '123 Test Street',
            'items': [
                {'product': self.product1.pk, 'quantity': 1}
            ]
        }
        
        response = self.client.post(url, data, format='json')
        self.assert_response_error(response, status.HTTP_401_UNAUTHORIZED)


class OrderCancellationAPITest(BaseAPITestCase):
    """Test order cancellation"""
    
    def setUp(self) -> None:
        """Set up cancellation test data"""
        super().setUp()
        
        category = Category.objects.create(name='Test', slug='test')
        self.product = Product.objects.create(
            name='Test Product',
            sku='TEST-001',
            price=Decimal('100.00'),
            category=category,
            stock_quantity=10
        )
        
        # Create order with items
        self.order = Order.objects.create(
            customer=self.test_customer,
            delivery_address='Test Address'
        )
        
        self.order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=3
        )
        
        # Reduce stock to simulate order processing
        self.product.reduce_stock(3)
        self.assertEqual(self.product.stock_quantity, 7)
    
    def test_cancel_order_success(self) -> None:
        """Test successful order cancellation with stock restoration"""
        self.authenticate()
        
        url = reverse('order-cancel', kwargs={'pk': self.order.pk})
        response = self.client.post(url)
        
        self.assert_response_success(response)
        
        # Verify order status changed
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.CANCELLED)
        
        # Verify stock was restored
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)
    
    def test_cancel_order_wrong_status(self) -> None:
        """Test cancellation fails for non cancellable orders"""
        self.authenticate()
        
        # Mark order as shipped
        self.order.status = Order.SHIPPED
        self.order.save()
        
        url = reverse('order-cancel', kwargs={'pk': self.order.pk})
        response = self.client.post(url)
        
        self.assert_response_error(response, status.HTTP_400_BAD_REQUEST)
        
        # Verify order status unchanged
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.SHIPPED)
    
    def test_cancel_order_unauthorized(self) -> None:
        """Test user cannot cancel other customer's orders"""
        # Create different customer
        other_user = User.objects.create_user(
            username='other',
            email='other@example.com',
            password='pass'
        )
        other_customer = Customer.objects.create(
            user=other_user,
            phone_number='+254700999999'
        )
        
        # Authenticate as original user
        self.authenticate()
        
        # Try to cancel other customer's order
        other_order = Order.objects.create(
            customer=other_customer,
            delivery_address='Other Address'
        )
        
        url = reverse('order-cancel', kwargs={'pk': other_order.pk})
        response = self.client.post(url)
        
        self.assert_response_error(response, status.HTTP_404_NOT_FOUND)


class OrderListAPITest(BaseAPITestCase):
    """Test order listing"""
    
    def setUp(self) -> None:
        """Set up list test data"""
        super().setUp()
        
        category = Category.objects.create(name='Test', slug='test')
        product = Product.objects.create(
            name='Test Product',
            sku='TEST-001',
            price=Decimal('50.00'),
            category=category,
            stock_quantity=10
        )
        
        # Create orders for current customer
        self.order1 = Order.objects.create(customer=self.test_customer)
        self.order2 = Order.objects.create(customer=self.test_customer)
        
        # Create order for different customer
        other_user = User.objects.create_user('other', 'other@test.com', 'pass')
        other_customer = Customer.objects.create(user=other_user, phone_number='+254700999999')
        self.other_order = Order.objects.create(customer=other_customer)
    
    def test_list_orders_customer_isolation(self) -> None:
        """Test customers only see their own orders"""
        self.authenticate()
        
        url = reverse('order-list')
        response = self.client.get(url)
        
        self.assert_response_success(response)
        
        data = self.get_json_response(response)
        orders = data['results']

        self.assertEqual(len(orders), 2)
        order_ids = [o['id'] for o in orders]
        self.assertIn(self.order1.pk, order_ids)
        self.assertIn(self.order2.pk, order_ids)
        self.assertNotIn(self.other_order.pk, order_ids)
    
    def test_order_summary_statistics(self) -> None:
        """Test order summary endpoint"""
        self.authenticate()

        self.order1.status = Order.DELIVERED
        self.order1.total_amount = Decimal('100.00')
        self.order1.save()
        
        self.order2.status = Order.PENDING
        self.order2.total_amount = Decimal('50.00')
        self.order2.save()
        
        url = reverse('order-summary')
        response = self.client.get(url)
        
        self.assert_response_success(response)
        
        data = self.get_json_response(response)

        self.assertEqual(data['total_orders'], 2)
        self.assertEqual(data['pending_orders'], 1)
        self.assertEqual(data['completed_orders'], 1)
        self.assertEqual(Decimal(data['total_spent']), Decimal('100.00'))


@pytest.mark.django_db  
class OrderAPIPytestTest:
    """Pytest API tests"""
    
    def test_order_creation_workflow(self, authenticated_client, test_customer) -> None:
        """Test complete order creation workflow"""
        # Create product
        category = Category.objects.create(name='Test', slug='test')
        product = Product.objects.create(
            name='Test Product',
            sku='TEST-001',
            price=Decimal('99.99'),
            category=category,
            stock_quantity=5
        )
        
        url = reverse('order-list')
        data = {
            'delivery_address': '123 Pytest Street',
            'items': [
                {'product': product.pk, 'quantity': 2}
            ]
        }
        
        response = authenticated_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert Order.objects.count() == 1
        
        order = Order.objects.first()
        assert order is not None
        assert order.customer == test_customer
        assert order.items.count() == 1
        
        # Verify stock reduction
        product.refresh_from_db()
        assert product.stock_quantity == 3  # 5 - 2
    
    def test_order_access_control(self, api_client, user_factory, customer_factory) -> None:
        """Test order access control between customers"""
        # Create two customers
        customer1 = customer_factory()
        customer2 = customer_factory()
        
        # Create order for customer1
        order = Order.objects.create(customer=customer1)
        
        # Authenticate as customer2
        from order_system.authentication import generate_jwt_token
        token = generate_jwt_token(customer2.user)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Try to access customer1's order
        url = reverse('order-detail', kwargs={'pk': order.pk})
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND