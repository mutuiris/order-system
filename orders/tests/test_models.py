"""
Tests for Order models
Tests order workflow and calculations
"""
import pytest
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth.models import User

from customers.models import Customer
from products.models import Category, Product
from orders.models import Order, OrderItem


class OrderModelTest(TestCase):
    """Test Order model business logic"""
    
    def setUp(self) -> None:
        """Set up essential test data"""
        # User and customer
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.customer = Customer.objects.create(
            user=self.user,
            phone_number='+254700123456'
        )
        
        # Product for testing
        category = Category.objects.create(name='Test', slug='test')
        self.product = Product.objects.create(
            name='Test Product',
            sku='TEST-001',
            price=Decimal('100.00'),
            category=category,
            stock_quantity=10
        )
    
    def test_order_creation_generates_order_number(self) -> None:
        """Test order automatically generates unique order number"""
        order = Order.objects.create(customer=self.customer)
        
        self.assertIsNotNone(order.order_number)
        self.assertTrue(order.order_number.startswith('ORD-'))
        self.assertEqual(len(order.order_number), 17)
    
    def test_order_total_calculations(self) -> None:
        """Test order total calculations"""
        order = Order.objects.create(customer=self.customer)
        
        # Add order item
        OrderItem.objects.create(
            order=order,
            product=self.product,
            quantity=2
        )
        
        # Calculate totals
        order.calculate_totals()
        
        # Verify calculations
        expected_subtotal = Decimal('200.00')
        expected_tax = Decimal('32.00')
        expected_total = Decimal('232.00')
        
        self.assertEqual(order.subtotal, expected_subtotal)
        self.assertEqual(order.tax_amount, expected_tax)
        self.assertEqual(order.total_amount, expected_total)
    
    def test_order_status_transitions(self) -> None:
        """Test order status workflow"""
        order = Order.objects.create(customer=self.customer)
        
        # Test initial status
        self.assertEqual(order.status, Order.PENDING)
        
        # Test can be cancelled logic
        self.assertTrue(order.can_be_cancelled)
        
        # Mark as confirmed
        order.mark_as_confirmed()
        self.assertEqual(order.status, Order.CONFIRMED)
        self.assertTrue(order.can_be_cancelled)
        
        # Test shipped status cannot be cancelled
        order.status = Order.SHIPPED
        order.save()
        self.assertFalse(order.can_be_cancelled)
    
    def test_order_item_count_property(self) -> None:
        """Test item_count calculation"""
        order = Order.objects.create(customer=self.customer)
        
        # Add multiple items
        OrderItem.objects.create(order=order, product=self.product, quantity=2)
        OrderItem.objects.create(order=order, product=self.product, quantity=3)
        
        self.assertEqual(order.item_count, 5)


class OrderItemModelTest(TestCase):
    """Test OrderItem business logic"""
    
    def setUp(self) -> None:
        """Set up test data"""
        user = User.objects.create_user('test', 'test@example.com', 'pass')
        self.customer = Customer.objects.create(user=user, phone_number='+254700123456')
        self.order = Order.objects.create(customer=self.customer)
        
        category = Category.objects.create(name='Test', slug='test')
        self.product = Product.objects.create(
            name='Test Product',
            sku='TEST-001', 
            price=Decimal('50.00'),
            category=category,
            stock_quantity=10
        )
    
    def test_order_item_snapshot_fields(self) -> None:
        """Test price snapshot preservation"""
        item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=2
        )

        # Verify snapshot fields are populated
        self.assertEqual(item.product_name, 'Test Product')
        self.assertEqual(item.product_sku, 'TEST-001')
        self.assertEqual(item.unit_price, Decimal('50.00'))
        self.assertEqual(item.line_total, Decimal('100.00'))
        
        # Change product price
        self.product.price = Decimal('75.00')
        self.product.save()

        item.refresh_from_db()
        self.assertEqual(item.unit_price, Decimal('50.00'))
    
    def test_order_item_line_total_calculation(self) -> None:
        """Test line total calculation"""
        item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=3
        )
        
        expected_total = Decimal('150.00')
        self.assertEqual(item.line_total, expected_total)
    
    def test_order_item_savings_calculation(self) -> None:
        """Test savings amount when current price is higher"""
        item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=2
        )

        # Increase current product price
        self.product.price = Decimal('60.00')
        self.product.save()

        expected_savings = Decimal('20.00')
        self.assertEqual(item.savings_amount, expected_savings)

        self.product.price = Decimal('40.00')
        self.product.save()
        self.assertEqual(item.savings_amount, Decimal('0.00'))


class OrderWorkflowTest(TestCase):
    """Test complete order workflow"""
    
    def setUp(self) -> None:
        """Set up workflow test data"""
        user = User.objects.create_user('workflow', 'workflow@test.com', 'pass')
        self.customer = Customer.objects.create(user=user, phone_number='+254700123456')
        
        category = Category.objects.create(name='Electronics', slug='electronics')
        self.product = Product.objects.create(
            name='iPhone',
            sku='IPH-001',
            price=Decimal('999.00'),
            category=category,
            stock_quantity=5
        )
    
    def test_complete_order_workflow(self) -> None:
        """Test end to end order creation and processing"""
        # Create order
        order = Order.objects.create(
            customer=self.customer,
            delivery_address='123 Test Street'
        )
        
        # Add items
        item = OrderItem.objects.create(
            order=order,
            product=self.product,
            quantity=2
        )
        
        # Calculate totals
        order.calculate_totals()
        
        # Verify order state
        self.assertEqual(order.subtotal, Decimal('1998.00'))
        self.assertEqual(order.tax_amount, Decimal('319.68'))
        self.assertEqual(order.total_amount, Decimal('2317.68'))
        
        # Confirm order
        order.mark_as_confirmed()
        self.assertEqual(order.status, Order.CONFIRMED)
    
    def test_stock_reduction_on_order_creation(self) -> None:
        """Test stock is reduced when order item is created"""
        original_stock = self.product.stock_quantity
        
        order = Order.objects.create(customer=self.customer)
        OrderItem.objects.create(
            order=order,
            product=self.product,
            quantity=2
        )
        
        # Manually reduce stock
        success = self.product.reduce_stock(2)
        
        self.assertTrue(success)
        self.assertEqual(self.product.stock_quantity, original_stock - 2)
    
    def test_order_cancellation_restores_stock(self) -> None:
        """Test stock restoration on order cancellation"""
        # Create order and reduce stock
        order = Order.objects.create(customer=self.customer)
        item = OrderItem.objects.create(
            order=order,
            product=self.product,
            quantity=3
        )
        
        self.product.reduce_stock(3)
        self.assertEqual(self.product.stock_quantity, 2)
        
        # Cancel order which restores stock
        self.product.stock_quantity += item.quantity
        self.product.save()
        order.status = Order.CANCELLED
        order.save()
        
        self.assertEqual(self.product.stock_quantity, 5)
        self.assertEqual(order.status, Order.CANCELLED)


@pytest.mark.django_db
class OrderModelPytestTest:
    """Pytest tests for orders"""
    
    def test_order_number_uniqueness(self) -> None:
        """Test order numbers are unique"""
        user = User.objects.create_user('test', 'test@example.com', 'pass')
        customer = Customer.objects.create(user=user, phone_number='+254700123456')
        
        order1 = Order.objects.create(customer=customer)
        order2 = Order.objects.create(customer=customer)
        
        assert order1.order_number != order2.order_number
        assert len(order1.order_number) == 17
        assert order1.order_number.startswith('ORD-')
    
    def test_tax_calculation_accuracy(self) -> None:
        """Test tax calculation precision"""
        user = User.objects.create_user('tax', 'tax@test.com', 'pass')
        customer = Customer.objects.create(user=user, phone_number='+254700123456')
        order = Order.objects.create(customer=customer)
        
        category = Category.objects.create(name='Test', slug='test')
        product = Product.objects.create(
            name='Tax Test Product',
            sku='TAX-001',
            price=Decimal('99.99'),
            category=category,
            stock_quantity=10
        )

        OrderItem.objects.create(order=order, product=product, quantity=1)
        order.calculate_totals()

        expected_tax = Decimal('15.99')
        expected_total = Decimal('115.98')
        
        assert order.tax_amount == expected_tax
        assert order.total_amount == expected_total