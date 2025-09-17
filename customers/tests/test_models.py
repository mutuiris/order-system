"""
Unit tests for Customer model
Tests model creation, properties, methods, and business logic
"""
import pytest
from django.test import TestCase
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.core.exceptions import ValidationError

from customers.models import Customer


class CustomerModelTest(TestCase):
    """Test Customer model functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            first_name='John',
            last_name='Doe'
        )
    
    def test_customer_creation(self):
        """Test basic customer creation"""
        customer = Customer.objects.create(
            user=self.user,
            phone_number='+254700123456'
        )
        
        self.assertEqual(customer.user, self.user)
        self.assertEqual(customer.phone_number, '+254700123456')
        self.assertTrue(customer.is_active)
        self.assertIsNotNone(customer.created_at)
        self.assertIsNotNone(customer.updated_at)
    
    def test_customer_str_representation(self):
        """Test string representation of customer"""
        customer = Customer.objects.create(
            user=self.user,
            phone_number='+254700123456'
        )
        
        expected_str = f"{self.user.get_full_name()} ({self.user.email})"
        self.assertEqual(str(customer), expected_str)
    
    def test_customer_str_with_no_full_name(self):
        """Test string representation when user has no full name"""
        user_no_name = User.objects.create_user(
            username='noname',
            email='noname@example.com',
            password='testpass123'
        )
        
        customer = Customer.objects.create(
            user=user_no_name,
            phone_number='+254700123456'
        )
        
        expected_str = f" ({user_no_name.email})"
        self.assertEqual(str(customer), expected_str)
    
    def test_full_name_property(self):
        """Test full_name property"""
        customer = Customer.objects.create(
            user=self.user,
            phone_number='+254700123456'
        )
        
        self.assertEqual(customer.full_name, 'John Doe')
    
    def test_full_name_property_fallback_to_username(self):
        """Test full name property falls back to username when no first or last name"""
        user_no_name = User.objects.create_user(
            username='uniqueuser',
            email='unique@example.com',
            password='testpass123'
        )
        
        customer = Customer.objects.create(
            user=user_no_name,
            phone_number='+254700123456'
        )
        
        self.assertEqual(customer.full_name, 'uniqueuser')
    
    def test_email_property(self):
        """Test email property"""
        customer = Customer.objects.create(
            user=self.user,
            phone_number='+254700123456'
        )
        
        self.assertEqual(customer.email, 'test@example.com')
    
    def test_customer_user_relationship(self):
        """Test one-to-one relationship with User"""
        customer = Customer.objects.create(
            user=self.user,
            phone_number='+254700123456'
        )
        
        # Test forward relationship
        self.assertEqual(customer.user, self.user)
        
        # Test reverse relationship
        reverse_customer = Customer.objects.get(user=self.user)
        self.assertEqual(reverse_customer, customer)
    
    def test_customer_unique_user_constraint(self):
        """Test that each user can have only one customer profile"""
        # Create first customer
        Customer.objects.create(
            user=self.user,
            phone_number='+254700123456'
        )
        
        # Try to create second customer with same user
        with self.assertRaises(IntegrityError):
            Customer.objects.create(
                user=self.user,
                phone_number='+254700654321'
            )
    
    def test_customer_default_values(self):
        """Test default field values"""
        customer = Customer.objects.create(
            user=self.user,
            phone_number='+254700123456'
        )
        
        self.assertTrue(customer.is_active)
    
    def test_customer_inactive_state(self):
        """Test setting customer as inactive"""
        customer = Customer.objects.create(
            user=self.user,
            phone_number='+254700123456',
            is_active=False
        )
        
        self.assertFalse(customer.is_active)
    
    def test_customer_phone_number_formats(self):
        """Test various phone number formats are accepted"""
        phone_numbers = [
            '+254700123456',
            '254700123456',
            '0700123456',
            '+1234567890123456789',
            '123',
        ]
        
        for i, phone in enumerate(phone_numbers):
            user = User.objects.create_user(
                username=f'user{i}',
                email=f'user{i}@example.com',
                password='testpass123'
            )
            
            customer = Customer.objects.create(
                user=user,
                phone_number=phone
            )
            
            self.assertEqual(customer.phone_number, phone)
    
    def test_customer_ordering(self):
        """Test customer model ordering"""
        # Create multiple customers
        users_and_customers = []
        for i in range(3):
            user = User.objects.create_user(
                username=f'user{i}',
                email=f'user{i}@example.com',
                password='testpass123'
            )
            customer = Customer.objects.create(
                user=user,
                phone_number=f'+25470012345{i}'
            )
            users_and_customers.append(customer)

        customers = list(Customer.objects.all())

        for i in range(len(customers) - 1):
            self.assertGreaterEqual(
                customers[i].created_at,
                customers[i + 1].created_at
            )
    
    def test_customer_meta_options(self):
        """Test model Meta options"""
        customer = Customer.objects.create(
            user=self.user,
            phone_number='+254700123456'
        )
        
        # Test verbose names
        self.assertEqual(customer._meta.verbose_name, 'Customer')
        self.assertEqual(customer._meta.verbose_name_plural, 'Customers')
        
        # Test ordering
        self.assertEqual(customer._meta.ordering, ['-created_at'])
    
    def test_customer_cascade_deletion(self):
        """Test that customer is deleted when user is deleted"""
        customer = Customer.objects.create(
            user=self.user,
            phone_number='+254700123456'
        )
        
        customer_pk = customer.pk
        
        # Delete the user
        self.user.delete()
        
        # Customer should also be deleted
        with self.assertRaises(Customer.DoesNotExist):
            Customer.objects.get(pk=customer_pk)
    
    def test_customer_save_and_update(self):
        """Test saving and updating customer"""
        customer = Customer.objects.create(
            user=self.user,
            phone_number='+254700123456'
        )
        
        original_updated_at = customer.updated_at
        original_created_at = customer.created_at
        
        # Update phone number
        customer.phone_number = '+254700654321'
        customer.save()
        
        # Refresh from database
        customer.refresh_from_db()
        
        # Check updated values
        self.assertEqual(customer.phone_number, '+254700654321')
        self.assertEqual(customer.created_at, original_created_at)
        self.assertGreater(customer.updated_at, original_updated_at)


@pytest.mark.django_db
class CustomerModelPytestTest:
    """Pytest-style tests for Customer model"""
    
    def test_customer_creation_with_pytest(self):
        """Test customer creation using pytest fixtures"""
        user = User.objects.create_user(
            username='pytestuser',
            email='pytest@example.com',
            password='testpass123'
        )
        
        customer = Customer.objects.create(
            user=user,
            phone_number='+254700123456'
        )
        
        assert customer.user == user
        assert customer.phone_number == '+254700123456'
        assert customer.is_active is True
    
    def test_customer_properties(self):
        """Test customer properties using pytest"""
        user = User.objects.create_user(
            username='proptest',
            email='prop@example.com',
            password='testpass123',
            first_name='Prop',
            last_name='Test'
        )
        
        customer = Customer.objects.create(
            user=user,
            phone_number='+254700123456'
        )
        
        assert customer.full_name == 'Prop Test'
        assert customer.email == 'prop@example.com'
        assert str(customer) == 'Prop Test (prop@example.com)'