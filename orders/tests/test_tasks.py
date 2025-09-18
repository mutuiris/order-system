"""
Tests for Order notification tasks
Tests SMS and Email notifications with mockings
"""
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from django.contrib.auth.models import User
from django.test import TestCase

from customers.models import Customer
from orders.models import Order, OrderItem
from orders.tasks import (send_admin_email, send_order_notifications,
                          send_order_sms)
from products.models import Category, Product


class OrderNotificationTaskTest(TestCase):
    """Test order notification tasks"""
    
    def setUp(self) -> None:
        """Set up notification test data"""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        
        self.customer = Customer.objects.create(
            user=user,
            phone_number='+254700123456'
        )
        
        # Create order with item
        category = Category.objects.create(name='Electronics', slug='electronics')
        product = Product.objects.create(
            name='iPhone 15',
            sku='IPH-15',
            price=Decimal('999.00'),
            category=category,
            stock_quantity=10
        )
        
        self.order = Order.objects.create(
            customer=self.customer,
            delivery_address='123 Test Street, Nairobi'
        )
        
        OrderItem.objects.create(
            order=self.order,
            product=product,
            quantity=2
        )
        
        self.order.calculate_totals()
    
    @patch('order_system.services.sms_service.sms_service')
    def test_send_order_sms_success(self, mock_sms_service) -> None:
        """Test successful SMS notification sending"""
        # Mock SMS service success response
        mock_sms_service.send_sms.return_value = {
            'success': True,
            'message': 'SMS sent successfully',
            'sent_to': ['+254700123456']
        }
        
        # Call SMS task
        result = send_order_sms(self.order.pk)

        mock_sms_service.send_sms.assert_called_once()
        
        call_args = mock_sms_service.send_sms.call_args
        phone_number, message = call_args[0]
        
        self.assertEqual(phone_number, '+254700123456')
        self.assertIn(self.order.order_number, message)
        self.assertIn('KES 2317.68', message)
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['order_number'], self.order.order_number)
        
        # Verify SMS sent flag is updated
        self.order.refresh_from_db()
        self.assertTrue(self.order.sms_sent)
    
    @patch('order_system.services.sms_service.sms_service')
    def test_send_order_sms_failure(self, mock_sms_service) -> None:
        """Test SMS notification failure handling"""
        # Mock SMS service failure
        mock_sms_service.send_sms.return_value = {
            'success': False,
            'error': 'SMS sending failed'
        }
        
        # Call SMS task
        with self.assertRaises(Exception):
            send_order_sms(self.order.pk)
        
        # Verify SMS sent flag is not updated
        self.order.refresh_from_db()
        self.assertFalse(self.order.sms_sent)
    
    @patch('django.core.mail.send_mail')
    def test_send_admin_email_success(self, mock_send_mail) -> None:
        """Test successful admin email notification"""
        # Mock email sending success
        mock_send_mail.return_value = True
        
        # Call email task
        result = send_admin_email(self.order.pk)
        
        # Verify email was sent with correct parameters
        mock_send_mail.assert_called_once()
        
        call_args = mock_send_mail.call_args
        kwargs = call_args[1]
        
        # Verify email content
        self.assertIn(self.order.order_number, kwargs['subject'])
        self.assertIn('KES 2317.68', kwargs['subject'])
        self.assertIn('Test User', kwargs['message'])
        self.assertIn(self.customer.phone_number, kwargs['message'])
        
        # Verify result
        self.assertTrue(result['success'])
        
        # Verify email sent flag is updated
        self.order.refresh_from_db()
        self.assertTrue(self.order.email_sent)
    
    @patch('django.core.mail.send_mail')
    def test_send_admin_email_failure(self, mock_send_mail) -> None:
        """Test admin email failure handling"""
        # Mock email sending failure
        mock_send_mail.return_value = False
        
        # Call email task
        with self.assertRaises(Exception):
            send_admin_email(self.order.pk)
        
        # Verify email sent flag is not updated
        self.order.refresh_from_db()
        self.assertFalse(self.order.email_sent)
    
    def test_notification_task_nonexistent_order(self) -> None:
        """Test notification tasks handle non-existent orders"""
        nonexistent_id = 99999
        
        # Test SMS task
        result = send_order_sms(nonexistent_id)
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Order not found')
        
        # Test email task
        result = send_admin_email(nonexistent_id)
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Order not found')
    
    @patch('orders.tasks.send_order_sms.delay')
    @patch('orders.tasks.send_admin_email.delay')
    def test_send_order_notifications_coordinator(self, mock_email_task, mock_sms_task) -> None:
        """Test main notification coordinator task"""
        # Mock task returns
        mock_sms_task.return_value = Mock(id='sms-task-123')
        mock_email_task.return_value = Mock(id='email-task-456')
        
        # Call coordinator task
        result = send_order_notifications(self.order.pk)
        
        # Verify both tasks were scheduled
        mock_sms_task.assert_called_once_with(self.order.pk)
        mock_email_task.assert_called_once_with(self.order.pk)
        
        # Verify result contains task IDs
        self.assertEqual(result['order_id'], self.order.pk)
        self.assertEqual(result['order_number'], self.order.order_number)
        self.assertEqual(result['sms_task_id'], 'sms-task-123')
        self.assertEqual(result['email_task_id'], 'email-task-456')
        self.assertIn('successfully', result['message'])


class OrderNotificationIntegrationTest(TestCase):
    """Integration test for notification workflow"""
    
    def setUp(self) -> None:
        """Set up integration test data"""
        user = User.objects.create_user('integration', 'integration@test.com', 'pass')
        self.customer = Customer.objects.create(user=user, phone_number='+254700123456')
        self.order = Order.objects.create(customer=self.customer)
    
    @patch('orders.tasks.send_order_notifications.delay')
    def test_mark_as_confirmed_triggers_notifications(self, mock_notifications) -> None:
        """Test that marking order as confirmed triggers notifications"""
        # Mark order as confirmed
        self.order.mark_as_confirmed()
        
        # Verify notifications were triggered
        mock_notifications.assert_called_once_with(self.order.pk)
        
        # Verify order status changed
        self.assertEqual(self.order.status, Order.CONFIRMED)


@pytest.mark.django_db
class OrderTasksPytestTest:
    """Pytest notification task tests"""
    
    @patch('order_system.services.sms_service.sms_service')
    def test_sms_notification_message_format(self, mock_sms_service, test_customer) -> None:
        """Test SMS message format is correct"""
        # Mock SMS service
        mock_sms_service.send_sms.return_value = {'success': True}
        
        # Create order
        order = Order.objects.create(customer=test_customer)
        order.total_amount = Decimal('150.00')
        order.save()
        
        # Send SMS
        send_order_sms(order.pk)
        
        # Verify message format
        call_args = mock_sms_service.send_sms.call_args[0]
        message = call_args[1]
        
        assert 'Order confirmed!' in message
        assert order.order_number in message
        assert 'KES 150.00' in message
        assert 'Thank you' in message
    
    @patch('django.core.mail.send_mail')
    def test_admin_email_contains_order_details(self, mock_send_mail, test_customer) -> None:
        """Test admin email contains all required order details"""
        mock_send_mail.return_value = True
        
        # Create order with details
        order = Order.objects.create(
            customer=test_customer,
            delivery_address='123 Admin Test Street',
            delivery_notes='Test admin notes',
            total_amount=Decimal('299.99')
        )
        order.save()
        
        # Send admin email
        send_admin_email(order.pk)
        
        # Verify email content
        call_kwargs = mock_send_mail.call_args[1]
        email_body = call_kwargs['message']
        
        assert order.order_number in email_body
        assert test_customer.full_name in email_body
        assert test_customer.phone_number in email_body
        assert '123 Admin Test Street' in email_body
        assert 'Test admin notes' in email_body
        assert 'KES 299.99' in email_body