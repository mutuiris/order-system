"""
Test data factories for customers
"""
import factory
import factory.django
from django.contrib.auth.models import User
from factory.declarations import LazyAttribute, Sequence, SubFactory
from factory.faker import Faker
from factory.helpers import lazy_attribute, post_generation

from customers.models import Customer


class UserFactory(factory.django.DjangoModelFactory):
    """Factory for creating User instances"""

    class Meta: # type: ignore
        model = User

    username = Sequence(lambda n: f'user{n}')
    email = LazyAttribute(lambda obj: f'{obj.username}@example.com')
    first_name = Faker('first_name')
    last_name = Faker('last_name')
    is_active = True
    is_staff = False
    is_superuser = False

    @post_generation
    def password(obj, create, extracted, **kwargs):
        """Set password for created user"""
        if not create:
            return

        password = extracted or 'testpass123'
        obj.set_password(password) # type: ignore
        obj.save() # type: ignore


class AdminUserFactory(UserFactory):
    """Factory for creating admin User instances"""

    is_staff = True
    is_superuser = True
    username = Sequence(lambda n: f'admin{n}')
    email = LazyAttribute(lambda obj: f'{obj.username}@admin.example.com')


class CustomerFactory(factory.django.DjangoModelFactory):
    """Factory for creating Customer instances"""

    class Meta: # type: ignore
        model = Customer

    user = SubFactory(UserFactory)
    is_active = True

    @lazy_attribute
    def phone_number(self):
        """Generate Kenyan phone number format"""
        import random
        return f'+2547{random.randint(10000000, 99999999)}'


class InactiveCustomerFactory(CustomerFactory):
    """Factory for creating inactive Customer instances"""

    is_active = False


# Utility functions for test scenarios
def create_user_with_customer(username=None, email=None, phone_number=None, **kwargs):
    """
    Create a user with associated customer profile
    """
    user_kwargs = {}
    customer_kwargs = {}

    user_fields = {'username', 'email', 'first_name',
                   'last_name', 'is_active', 'is_staff', 'is_superuser'}

    for key, value in kwargs.items():
        if key in user_fields:
            user_kwargs[key] = value
        else:
            customer_kwargs[key] = value

    if username:
        user_kwargs['username'] = username
    if email:
        user_kwargs['email'] = email
    if phone_number:
        customer_kwargs['phone_number'] = phone_number

    # Create user
    user = UserFactory(**user_kwargs)

    # Create customer
    customer = CustomerFactory(user=user, **customer_kwargs)

    return user, customer


def create_multiple_customers(count=5, **kwargs):
    """
    Create multiple customers for testing
    """
    customers = []

    for i in range(count):
        customer_kwargs = kwargs.copy()
        customer_kwargs.setdefault('username', f'testuser{i}')

        user, customer = create_user_with_customer(**customer_kwargs)
        customers.append((user, customer))

    return customers


def create_authenticated_user(username=None, email=None):
    """
    Create user with customer profile and return JWT token
    """
    user, customer = create_user_with_customer(username=username, email=email)

    from order_system.authentication import generate_jwt_token
    token = generate_jwt_token(user)

    return user, customer, token


def create_admin_user(username=None, email=None):
    """
    Create admin user with customer profile
    """
    admin_user = AdminUserFactory()
    if username:
        admin_user.username = username
    if email:
        admin_user.email = email
    admin_user.save()

    customer = CustomerFactory(user=admin_user)

    return admin_user, customer


# Test data builders
class CustomerTestDataBuilder:
    """Builder pattern for creating complex customer test data"""

    def __init__(self):
        self.user_data = {}
        self.customer_data = {}

    def with_name(self, first_name, last_name):
        """Set customer name"""
        self.user_data.update({
            'first_name': first_name,
            'last_name': last_name
        })
        return self

    def with_email(self, email):
        """Set customer email"""
        self.user_data['email'] = email
        return self

    def with_phone(self, phone_number):
        """Set customer phone number"""
        self.customer_data['phone_number'] = phone_number
        return self

    def inactive(self):
        """Make customer inactive"""
        self.customer_data['is_active'] = False
        return self

    def admin(self):
        """Make user admin"""
        self.user_data.update({
            'is_staff': True,
            'is_superuser': True
        })
        return self

    def build(self):
        """Build the customer"""
        user = UserFactory(**self.user_data)
        customer = CustomerFactory(user=user, **self.customer_data)
        return user, customer


def create_oauth_user_data():
    """Create mock OAuth user data for testing"""
    return {
        'username': 'oauthuser',
        'email': 'oauth@google.com',
        'first_name': 'OAuth',
        'last_name': 'User',
        'provider': 'google-oauth2',
        'uid': '123456789',
    }


def create_jwt_test_data():
    """Create test data for JWT authentication tests"""
    user, customer = create_user_with_customer(
        username='jwtuser',
        email='jwt@example.com',
        first_name='JWT',
        last_name='User'
    )

    from order_system.authentication import generate_jwt_token
    token = generate_jwt_token(user)

    return {
        'user': user,
        'customer': customer,
        'token': token,
        'auth_header': f'Bearer {token}'
    }


def create_customer_update_test_data():
    """Create test data for customer update scenarios"""
    user, customer = create_user_with_customer(
        first_name='Original',
        last_name='Name',
        phone_number='+254700123456'
    )

    update_data = {
        'first_name': 'Updated',
        'last_name': 'Name',
        'phone_number': '+254700999888'
    }

    return {
        'user': user,
        'customer': customer,
        'update_data': update_data
    }


def create_bulk_customers(count=100):
    """Create customers in bulk for performance testing"""
    users_data = []
    customers_data = []

    for i in range(count):
        user = UserFactory.build()
        users_data.append(user)

    # Bulk create users
    users = User.objects.bulk_create(users_data)

    for user in users:
        customer = CustomerFactory.build(user=user)
        customers_data.append(customer)

    customers = Customer.objects.bulk_create(customers_data)

    return users, customers
