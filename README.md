# Order System

A Django REST API service implementing customer authentication, hierarchical product catalogs, order processing, and asynchronous notifications.

## Features

- OpenID Connect authentication with Google OAuth2 and JWT token management
- Hierarchical product categories with unlimited nesting depth
- RESTful API with filtering, pagination, and comprehensive endpoint coverage
- Order processing workflow with inventory management and tax calculations
- Asynchronous SMS and email notifications via Celery task queue
- Comprehensive test suite with 80% coverage requirement and CI/CD pipeline
- Production-ready deployment with Docker containerization

## Technology Stack

**Backend Framework**: Django 5.2 with Django REST Framework  
**Database**: PostgreSQL 17 with hierarchical data modeling  
**Authentication**: Google OAuth2 with JWT token implementation  
**Task Queue**: Celery 5.5 with Redis broker for background processing  
**External APIs**: Africa's Talking SMS gateway, Gmail SMTP notifications  
**Testing**: pytest with factory patterns and coverage reporting  
**Deployment**: Docker Compose with multi-service architecture  
**CI/CD**: GitHub Actions with automated testing and deployment validation  

## Quick Start

### Prerequisites

- Docker 24.0+
- Docker Compose 2.0+

### Installation

1. Clone the repository:
```bash
git clone https://github.com/mutuiris/order-system.git
cd order-system
```

2. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration values
```

3. Start all services:
```bash
docker-compose up --build
```

4. Access the application:
- API Base URL: http://localhost:8000/api/v1/
- Django Admin: http://localhost:8000/admin/

## System Workflow

### Complete Order Processing Flow

1. **Customer Authentication**
   - Google OAuth2 authentication flow
   - JWT token generation for API access
   - Customer profile creation and management

2. **Product Catalog Management**
   - Hierarchical categories with unlimited depth
   - Product assignment to any category level
   - Average price calculation across category trees

3. **Order Processing**
   - Shopping cart creation with inventory validation
   - Automatic tax calculation (16% VAT)
   - Order confirmation with status tracking

4. **Notification System**
   - Asynchronous SMS notifications via Africa's Talking
   - Admin email notifications for new orders
   - Background processing with Celery task queue

### Category Hierarchy Example

```
All Products
├── Bakery
│   ├── Bread
│   └── Cookies
└── Produce
    ├── Fruits
    └── Vegetables
```

Products can be assigned to any category level, and average price calculations include all products in subcategories.

## API Reference

### Authentication Flow

**Initiate OAuth Login**
```bash
GET /api/v1/auth/login/
```

**Check Authentication Status**
```bash
GET /api/v1/auth/status/
Authorization: Bearer <jwt_token>
```

### Product Catalog

**Get Category Tree Structure**
```bash
GET /api/v1/categories/tree/
```

**Calculate Average Price for Category**
```bash
GET /api/v1/categories/bakery/avg_price/
```

**List Products with Filtering**
```bash
GET /api/v1/products/?category=1&min_price=10&max_price=100&search=bread
```

### Order Management

**Create Order**
```bash
POST /api/v1/orders/
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "delivery_address": "Westlands, Nairobi",
  "delivery_notes": "Call on arrival",
  "items": [
    {"product": 1, "quantity": 2},
    {"product": 2, "quantity": 1}
  ]
}
```

**List Customer Orders**
```bash
GET /api/v1/orders/
Authorization: Bearer <jwt_token>
```

**Cancel Order**
```bash
POST /api/v1/orders/{id}/cancel/
Authorization: Bearer <jwt_token>
```

## Database Design

### Data Models

**Customer Management**
- Customer profiles linked to Django User model
- Phone number storage for SMS notifications
- Google OAuth2 integration for authentication

**Product Catalog**
- Hierarchical categories with self-referencing foreign keys
- Automatic level calculation for unlimited nesting depth
- Product inventory tracking with availability logic

**Order Processing**
- Order workflow: PENDING → CONFIRMED → PROCESSING → SHIPPED → DELIVERED
- OrderItem price snapshots preserve pricing at time of purchase
- Automatic tax calculation and total computation
- Stock management with atomic inventory updates

### Business Rules

- **Inventory Management**: Stock reduced on order creation, restored on cancellation
- **Price Integrity**: OrderItems maintain original pricing regardless of product price changes
- **Tax Calculation**: 16% VAT automatically applied to all orders
- **Order Status**: Orders can only be cancelled in PENDING or CONFIRMED states
- **Data Protection**: Foreign key constraints prevent accidental data deletion

## Testing

### Test Execution

```bash
# Run complete test suite with coverage
pytest --cov=. --cov-report=term-missing --cov-report=html

# Run specific test categories
pytest -m unit  # Unit tests
pytest -m integration # Integration tests
pytest -m api # API endpoint tests
```

### Test Coverage

- **Coverage Requirement**: Minimum 80% code coverage enforced by CI/CD
- **Test Types**: Unit, integration, API endpoint, and authentication flow tests
- **Test Data**: Factory Boy patterns for consistent and reliable test data
- **Continuous Integration**: Automated testing on all commits and pull requests

### CI/CD Pipeline

GitHub Actions workflow includes:
- Multi-version Python testing (3.11, 3.12, 3.13)
- PostgreSQL 17 and Redis 7 service containers
- Automated test execution and coverage reporting
- Code formatting validation with Black
- Dependency caching for optimized build performance

## Development Setup

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run database migrations
python manage.py migrate

# Create superuser account
python manage.py createsuperuser

# Start development server
python manage.py runserver
```

### Background Task Processing

```bash
# Start Celery worker
celery -A order_system worker --loglevel=info

# Start Celery beat scheduler
celery -A order_system beat --loglevel=info
```

## Deployment

### Environment Configuration

Create `.env` file with required variables:

```bash
DEBUG=False
SECRET_KEY=your-secure-secret-key
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
DB_NAME=order_system
DB_USER=order_user
DB_PASSWORD=secure-password
DB_HOST=db
DB_PORT=5432
GOOGLE_OAUTH2_KEY=your-oauth-client-id
GOOGLE_OAUTH2_SECRET=your-oauth-client-secret
AFRICASTALKING_USERNAME=your-username
AFRICASTALKING_API_KEY=your-api-key
EMAIL_HOST_USER=your-smtp-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
CELERY_BROKER_URL=redis://redis:6379/0
```

### Production Deployment

```bash
# Deploy all services
docker-compose up -d --build

# Run database migrations
docker-compose exec web python manage.py migrate

# Collect static files
docker-compose exec web python manage.py collectstatic --noinput
```


## Documentation

For additional technical documentation, see the `docs/` directory:

### **API Reference**
**[API Documentation](docs/api.md)**
- Complete endpoint reference with request/response examples
- Authentication flow with OAuth2 and JWT implementation
- Error handling and response format specifications
- Pagination and filtering parameter details

### **System Architecture Guide**
**[Architecture Documentation](docs/architecture.md)**
- Technical implementation details and design patterns
- Database design and entity relationships
- Background task processing with Celery
- External service integration patterns
- Configuration management and deployment architecture

---
