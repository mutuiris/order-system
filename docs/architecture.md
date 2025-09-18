# System Architecture

This document outlines the architectural decisions, design patterns, and technical rationale behind the Order System.

## Architecture Overview

The system follows a **modular monolith** architecture pattern, organized into distinct Django applications with clear boundaries and responsibilities.

### High-Level Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Web Client    │    │   Mobile Client  │    │  Admin Panel    │
└─────────┬───────┘    └─────────┬────────┘    └─────────┬───────┘
          │                      │                       │
          └──────────────────────┼───────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │     Load Balancer       │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   Django Application    │
                    │   ┌─────────────────┐   │
                    │   │   REST API      │   │
                    │   │   (DRF)         │   │
                    │   └─────────────────┘   │
                    │   ┌─────────────────┐   │
                    │   │  Business Logic │   │
                    │   │  (Models/Views) │   │
                    │   └─────────────────┘   │
                    └────────────┬────────────┘
                                 │
            ┌────────────────────┼────────────────────┐
            │                    │                    │
   ┌────────▼────────┐  ┌───────▼────────┐  ┌───────▼────────┐
   │   PostgreSQL    │  │     Redis       │  │  Celery Workers │
   │   Database      │  │    Cache        │  │  (Background)   │
   └─────────────────┘  └────────────────┘  └─────────┬───────┘
                                                      │
                                              ┌───────▼────────┐
                                              │ External APIs  │
                                              │ - SMS Gateway  │
                                              │ - Email SMTP   │
                                              └────────────────┘
```

## Application Architecture

### Domain-Driven Design

The system is organized into three primary domains:

**Customer Domain (`customers/`)**
- User authentication and profile management
- OAuth2 integration and JWT token handling
- Customer-specific business rules and validation

**Product Domain (`products/`)**
- Product catalog management
- Hierarchical category system
- Inventory tracking and pricing logic

**Order Domain (`orders/`)**
- Order lifecycle management
- Payment processing and tax calculation
- Notification and fulfillment coordination

### Layered Architecture

```
┌─────────────────────────────────────────┐
│           Presentation Layer            │
│  ┌─────────────┐  ┌─────────────────┐   │
│  │ REST API    │  │ Django Admin    │   │
│  │ (DRF Views) │  │ Interface       │   │
│  └─────────────┘  └─────────────────┘   │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│            Business Layer               │
│  ┌─────────────┐  ┌─────────────────┐   │
│  │ Serializers │  │ Business Logic  │   │
│  │ Validation  │  │ (Model Methods) │   │
│  └─────────────┘  └─────────────────┘   │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│             Data Layer                  │
│  ┌─────────────┐  ┌─────────────────┐   │
│  │ Django ORM  │  │ Database        │   │
│  │ Models      │  │ (PostgreSQL)    │   │
│  └─────────────┘  └─────────────────┘   │
└─────────────────────────────────────────┘
```

## Database Design

### Entity Relationship Design

**Core Entities:**
- **User**: Django's built-in authentication model
- **Customer**: Extended user profile with business-specific fields
- **Category**: Self-referencing hierarchical structure
- **Product**: Catalog items with category associations
- **Order**: Transaction header with workflow status
- **OrderItem**: Line items with price snapshots

### Hierarchical Data Strategy

**Challenge**: Store unlimited-depth category hierarchies efficiently

**Solution**: Modified Adjacency List with level denormalization

```sql
-- Category table structure
CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(120) UNIQUE NOT NULL,
    parent_id INTEGER REFERENCES categories(id),
    level INTEGER DEFAULT 0,
    sort_order INTEGER DEFAULT 0
);

-- Automatic level calculation on save
-- Enables efficient depth-based queries
```

**Benefits:**
- Simple to understand and maintain
- Efficient for reads (common pattern)
- Supports unlimited nesting depth
- Fast ancestor/descendant queries

### Data Integrity Patterns

**Price Snapshots:**
```python
# OrderItem preserves pricing at time of purchase
class OrderItem(models.Model):
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    unit_price = models.DecimalField()  # Snapshot from product.price
    
    def save(self):
        if not self.unit_price:
            self.unit_price = self.product.price  # Capture current price
```

**Soft Relationships:**
```python
# PROTECT prevents accidental data loss
product = models.ForeignKey(Product, on_delete=models.PROTECT)
category = models.ForeignKey(Category, on_delete=models.PROTECT)
```

## Service Architecture

### Background Task Processing

**Pattern**: Producer-Consumer with Celery

```python
# Producer (Order creation)
def mark_as_confirmed(self):
    self.status = self.CONFIRMED
    self.save()
    send_order_notifications.delay(self.id)  # Async task

# Consumer (Celery worker)
@shared_task(bind=True, max_retries=3)
def send_order_sms(self, order_id):
    # Retry logic with exponential backoff
    try:
        # SMS sending logic
    except Exception as e:
        raise self.retry(countdown=60 * (2 ** self.request.retries))
```

**Benefits:**
- Non-blocking order confirmation
- Fault tolerance with retry mechanisms
- Scalable processing (add more workers)
- Monitoring and debugging capabilities

### External Service Integration

**SMS Service Abstraction:**
```python
class SMSService:
    def __init__(self):
        self.client = self._get_client()
    
    def send_sms(self, phone_number, message):
        # Standardized interface regardless of provider
        # Error handling and retry logic
        # Phone number validation and formatting
```

**Integration Patterns:**
- **Adapter Pattern**: Consistent interface for external APIs
- **Circuit Breaker**: Prevent cascade failures
- **Retry with Backoff**: Handle temporary failures
- **Fallback Mechanisms**: Graceful degradation

## Authentication Architecture

### OAuth2 + JWT Hybrid Approach

**Flow Design:**
```
1. Client → Google OAuth2 Authorization Server
2. Authorization Server → Callback with auth code  
3. Backend exchanges code for user info
4. Backend generates JWT token
5. Client uses JWT for subsequent API calls
```

**Technical Implementation:**
```python
# OAuth pipeline customization
SOCIAL_AUTH_PIPELINE = [
    'social_core.pipeline.social_auth.social_details',
    'social_core.pipeline.user.create_user',
    'order_system.auth_pipeline.create_customer_profile',  # Custom step
]

# JWT token generation
def generate_jwt_token(user):
    payload = {
        'user_id': user.pk,
        'email': user.email,
        'exp': datetime.now(timezone.utc) + timedelta(hours=24),
        'iat': datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
```

**Security Considerations:**
- Stateless authentication (no session storage)
- Short token expiration (24 hours)
- Secure token transmission (HTTPS only in production)
- No sensitive data in JWT payload

## Technical Decision Rationale

### Technology Choices

**Django REST Framework over FastAPI:**
- **Rationale**: Mature ecosystem, built-in admin, ORM integration
- **Trade-off**: Slightly slower performance for comprehensive features
- **Context**: Business application with complex data relationships

**PostgreSQL over NoSQL:**
- **Rationale**: ACID compliance, complex queries, hierarchical data
- **Trade-off**: Horizontal scaling complexity vs data consistency
- **Context**: Financial transactions require strong consistency

**Celery over Django-RQ:**
- **Rationale**: Advanced features (retries, monitoring, routing)
- **Trade-off**: More complex setup vs comprehensive task management
- **Context**: Production reliability requirements

**JWT over Session Authentication:**
- **Rationale**: Stateless, mobile-friendly, microservices-ready
- **Trade-off**: Token management complexity vs scalability
- **Context**: API-first architecture with multiple client types

### Design Pattern Decisions

**Repository Pattern: Not Implemented**
- **Decision**: Use Django ORM directly in views/serializers
- **Rationale**: Django ORM provides sufficient abstraction
- **Context**: Single database, straightforward queries

**CQRS Pattern: Not Implemented**
- **Decision**: Single model for read/write operations
- **Rationale**: Current scale doesn't justify complexity
- **Context**: Monolithic architecture, moderate traffic

**Event Sourcing: Partially Implemented**
- **Decision**: Order status changes tracked, not full event sourcing
- **Rationale**: Business audit requirements without full complexity
- **Context**: Order workflow tracking needed, not all domain events

## Scalability Considerations

### Horizontal Scaling Strategy

**Application Tier:**
```yaml
# Docker Compose scaling
version: '3.8'
services:
  web:
    image: order-system:latest
    deploy:
      replicas: 3  # Multiple app instances
      
  celery:
    image: order-system:latest
    deploy:
      replicas: 5  # Scale background processing
```

**Database Scaling:**
- **Current**: Single PostgreSQL instance
- **Next Step**: Read replicas for reporting queries
- **Long-term**: Sharding by customer_id or geographic region

**Caching Strategy:**
```python
# Redis caching layers
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://redis:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Cache usage patterns
@cache_page(60 * 15)  # API response caching
def category_tree_view(request):
    pass

# Database query caching
categories = cache.get_or_set(
    'category_hierarchy', 
    lambda: Category.objects.prefetch_related('children'),
    timeout=3600
)
```

### Performance Optimization

**Database Optimization:**
```python
# Query optimization patterns
products = Product.objects.select_related('category').prefetch_related('order_items')

# Database indexes
class Meta:
    indexes = [
        models.Index(fields=['category', 'is_active']),
        models.Index(fields=['created_at', 'status']),
    ]
```

**API Response Optimization:**
- Pagination for list endpoints (20 items per page)
- Field selection with sparse fieldsets
- Compression for large responses
- ETags for cache validation

## Monitoring and Observability

### Health Check Strategy

```python
def health_check():
    checks = {
        'database': check_database_connection(),
        'redis': check_redis_connection(), 
        'celery': check_celery_workers(),
        'external_apis': check_external_services(),
    }
    
    overall_status = 'healthy' if all(checks.values()) else 'degraded'
    return {'status': overall_status, 'checks': checks}
```

### Logging Architecture

```python
LOGGING = {
    'version': 1,
    'handlers': {
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'django.log',
            'formatter': 'verbose',
        },
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'orders.tasks': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
        },
    },
}
```

## Security Architecture

### Security Boundaries

**Input Validation:**
- Serializer-level validation for all API inputs
- Database constraint enforcement
- File upload restrictions and scanning

**Authentication & Authorization:**
- OAuth2 for user authentication
- JWT for session management
- Permission classes for endpoint access control

**Data Protection:**
- Environment variable configuration
- Database connection encryption
- HTTPS enforcement in production
- Sensitive data exclusion from logs

### Security Headers

```python
# Production security settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
X_FRAME_OPTIONS = 'DENY'
```

## Future Architecture Evolution

### Microservices Migration Path

**Phase 1**: Extract notification service
```
Order Service → Notification Service (SMS/Email)
Benefits: Independent scaling, technology diversity
```

**Phase 2**: Extract authentication service  
```
Centralized auth service for multiple applications
Benefits: Single sign-on, consistent security
```

**Phase 3**: Extract product catalog service
```
Dedicated catalog service with advanced search
Benefits: Search optimization, caching strategies
```

### Technology Evolution

**API Gateway Introduction:**
- Rate limiting and throttling
- Request/response transformation
- API versioning and routing

**Event-Driven Architecture:**
- Message queues for service communication  
- Event sourcing for audit trails
- CQRS for read/write separation

**Container Orchestration:**
- Kubernetes for production deployment
- Auto-scaling based on metrics
- Rolling deployments and health checks