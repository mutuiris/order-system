# System Architecture

This document outlines the architectural decisions and technical implementation of the Order System.

## Architecture Overview

The system follows a **modular monolith** architecture pattern, organized into distinct Django applications with clear boundaries.

### Application Structure
```
customers/     - User authentication and profile management
products/      - Product catalog and hierarchical categories  
orders/        - Order processing and workflow management
order_system/  - Core configuration and shared services
```

## Database Design

### Entity Relationships

**Core Models:**
- **User**: Django's built-in authentication
- **Customer**: Extended user profile with phone number
- **Category**: Self-referencing hierarchical structure
- **Product**: Catalog items with category associations
- **Order**: Transaction with status workflow
- **OrderItem**: Line items with price snapshots

### Hierarchical Categories

**Implementation**: Modified Adjacency List with level denormalization

```python
class Category(models.Model):
    name = models.CharField(max_length=100)
    parent = models.ForeignKey('self', null=True, blank=True)
    level = models.PositiveIntegerField(default=0)  # Auto-calculated
    
    def save(self, *args, **kwargs):
        if self.parent:
            self.level = self.parent.level + 1
        super().save(*args, **kwargs)
```

**Benefits:**
- Unlimited nesting depth
- Efficient ancestor/descendant queries
- Simple to understand and maintain

## Authentication Architecture

### OAuth2 + JWT Implementation

**Flow:**
1. Client requests Google OAuth2 login URL
2. User authenticates with Google
3. Callback creates/updates user and customer profile
4. Backend generates JWT token for API access

```python
# Custom pipeline step
def create_customer_profile(strategy, details, user=None, *args, **kwargs):
    if user and not hasattr(user, 'customer_profile'):
        Customer.objects.get_or_create(
            user=user, 
            defaults={'phone_number': details.get('phone_number', '+254700000000')}
        )
```

**JWT Token Generation:**
```python
def generate_jwt_token(user):
    payload = {
        'user_id': user.pk,
        'email': user.email,
        'exp': datetime.now(timezone.utc) + timedelta(hours=24),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
```

## Background Task Processing

### Celery Implementation

**Order Notification Flow:**
```python
# In Order model
def mark_as_confirmed(self):
    self.status = self.CONFIRMED
    self.save()
    send_order_notifications.delay(self.id)  # Async

# Celery tasks
@shared_task(bind=True, max_retries=3)
def send_order_sms(self, order_id):
    try:
        order = Order.objects.get(id=order_id)
        result = sms_service.send_sms(order.customer.phone_number, message)
        if result['success']:
            Order.objects.filter(id=order_id).update(sms_sent=True)
    except Exception as e:
        raise self.retry(countdown=60 * (2 ** self.request.retries))
```

**Task Coordination:**
```python
@shared_task
def send_order_notifications(order_id):
    sms_task = send_order_sms.delay(order_id)
    email_task = send_admin_email.delay(order_id)
    return {
        'sms_task_id': sms_task.id,
        'email_task_id': email_task.id
    }
```

## External Service Integration

### SMS Service (Africa's Talking)

```python
class SMSService:
    def __init__(self):
        self.username = settings.AFRICASTALKING_USERNAME
        self.api_key = settings.AFRICASTALKING_API_KEY
        
    def send_sms(self, phone_number, message):
        formatted_number = self.format_phone_number(phone_number)
        if not self.validate_phone_number(phone_number):
            return {'success': False, 'error': 'Invalid phone number'}
            
        client = africastalking.SMS
        response = client.send(message=message, recipients=[formatted_number])
        return {'success': True, 'message': 'SMS sent successfully'}
```

### Email Notifications

```python
@shared_task
def send_admin_email(order_id):
    order = Order.objects.get(id=order_id)
    subject = f"New Order: #{order.order_number} - KES {order.total_amount}"
    
    mail.send_mail(
        subject=subject,
        message=format_order_details(order),
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[settings.ADMIN_EMAIL]
    )
```

## API Design

### RESTful Architecture

**Endpoint Structure:**
```
/api/v1/categories/          - Category CRUD
/api/v1/categories/tree/     - Hierarchical tree view
/api/v1/products/           - Product catalog
/api/v1/orders/             - Order management
/api/v1/orders/{id}/cancel/ - Order actions
/api/v1/customer/me/        - Profile management
```

**Authentication Pattern:**
```python
# JWT Authentication class
class JWTAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        token = self.get_token_from_header(request)
        if token:
            user = self._authenticate_credentials(token)
            return (user, token)
        return None
```

## Data Integrity Patterns

### Price Snapshots
```python
class OrderItem(models.Model):
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    unit_price = models.DecimalField()  # Snapshot at time of order
    
    def save(self, *args, **kwargs):
        if not self.unit_price:
            self.unit_price = self.product.price  # Capture current price
        super().save(*args, **kwargs)
```

### Stock Management
```python
def create_order_with_items(self, validated_data):
    with transaction.atomic():
        # Reduce stock
        for item_data in items_data:
            product = item_data['product']
            quantity = item_data['quantity']
            
            if product.stock_quantity < quantity:
                raise ValidationError("Insufficient stock")
                
            product.stock_quantity -= quantity
            product.save()
```

## Configuration Management

### Environment-Based Settings
```python
# Core settings
DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'
SECRET_KEY = os.environ.get('SECRET_KEY', 'default-key')

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'order_system'),
        'USER': os.environ.get('DB_USER', 'order_user'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'order_pass'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

# Celery
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')

# SMS Configuration
AFRICASTALKING_USERNAME = os.environ.get('AFRICASTALKING_USERNAME', 'sandbox')
AFRICASTALKING_API_KEY = os.environ.get('AFRICASTALKING_API_KEY', '')
```

## Testing Architecture

### Test Structure
```python
# Base test classes
class BaseAPITestCase(APITestCase):
    def setUp(self):
        self.test_user = User.objects.create_user(...)
        self.test_customer = Customer.objects.create(...)
        self.jwt_token = generate_jwt_token(self.test_user)
    
    def authenticate(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.jwt_token}')
```

### Factory Pattern
```python
class OrderFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Order
    
    customer = factory.SubFactory(CustomerFactory)
    status = Order.PENDING
    delivery_address = factory.Faker('address')
```

## Deployment Architecture

### Docker Configuration
```yaml
# docker-compose.yml
services:
  db:
    image: postgres:17
    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
  
  redis:
    image: redis:7
  
  web:
    build: .
    depends_on: [db, redis]
    environment:
      - DB_HOST=db
      - CELERY_BROKER_URL=redis://redis:6379/0
  
  celery:
    build: .
    command: celery -A order_system worker --loglevel=info
    depends_on: [db, redis]
```

## Technical Decisions

### Technology Choices

**Django REST Framework:**
- Mature ecosystem with built-in admin interface
- Excellent ORM for complex relationships
- Comprehensive authentication and permissions

**PostgreSQL:**
- Excellent support for hierarchical data
- Advanced querying capabilities

**Celery + Redis:**
- Reliable background task processing
- Retry mechanisms with exponential backoff
- Task monitoring and debugging capabilities

**JWT Authentication:**
- Stateless authentication suitable for APIs
- Integrates well with OAuth2 flow

### Design Patterns

**Repository Pattern: Not Used**
- Django ORM provides sufficient abstraction
- Direct model usage in views/serializers

**Service Layer: Minimal**
- Business logic primarily in model methods
- External services wrapped in simple classes