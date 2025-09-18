"""
Test data factories for orders app
"""

import random
from decimal import Decimal

import factory
from factory.faker import Faker

from customers.tests.factories import CustomerFactory
from orders.models import Order, OrderItem
from products.tests.factories import ProductFactory


class OrderFactory(factory.django.DjangoModelFactory):
    """Factory for creating Order instances"""

    class Meta:  # type: ignore
        model = Order

    customer = factory.SubFactory(CustomerFactory)  # type: ignore
    delivery_address = Faker("address")
    delivery_notes = Faker("sentence", nb_words=6)
    status = Order.PENDING


class PendingOrderFactory(OrderFactory):
    """Factory for pending orders"""

    status = Order.PENDING


class ConfirmedOrderFactory(OrderFactory):
    """Factory for confirmed orders"""

    status = Order.CONFIRMED


class CancelledOrderFactory(OrderFactory):
    """Factory for cancelled orders"""

    status = Order.CANCELLED


class DeliveredOrderFactory(OrderFactory):
    """Factory for delivered orders"""

    status = Order.DELIVERED


class OrderItemFactory(factory.django.DjangoModelFactory):
    """Factory for creating OrderItem instances"""

    class Meta:  # type: ignore
        model = OrderItem

    order = factory.SubFactory(OrderFactory)  # type: ignore
    product = factory.SubFactory(ProductFactory)  # type: ignore
    quantity = Faker("random_int", min=1, max=5)


def create_order_with_items(
    customer=None, products_and_quantities=None, **order_kwargs
):
    """
    Create order with items
    """
    if not customer:
        customer = CustomerFactory()

    order = OrderFactory(customer=customer, **order_kwargs)

    if products_and_quantities:
        for product, quantity in products_and_quantities:
            OrderItemFactory(order=order, product=product, quantity=quantity)

    # Calculate totals
    order.calculate_totals()

    return order


def create_simple_order(total_amount=None):
    """
    Create simple order for testing
    """
    if total_amount:
        # total = subtotal + (subtotal * 0.16)
        # total = subtotal * 1.16
        # subtotal = total / 1.16
        subtotal = Decimal(str(total_amount)) / Decimal("1.16")
        product = ProductFactory(price=subtotal)
    else:
        product = ProductFactory(price=Decimal("100.00"))

    order = OrderFactory()
    OrderItemFactory(order=order, product=product, quantity=1)

    order.calculate_totals()
    return order


def create_order_workflow_scenario():
    """
    Create complete order scenario for workflow testing
    """
    customer = CustomerFactory()

    # Create products with known prices
    product1 = ProductFactory(
        name="iPhone 15", sku="IPH-15", price=Decimal("999.00"), stock_quantity=10
    )

    product2 = ProductFactory(
        name="MacBook Pro", sku="MBP-001", price=Decimal("1999.00"), stock_quantity=5
    )

    # Create order
    order = OrderFactory(customer=customer, delivery_address="123 Workflow Test Street")

    # Add items
    item1 = OrderItemFactory(order=order, product=product1, quantity=2)
    item2 = OrderItemFactory(order=order, product=product2, quantity=1)

    # Calculate totals
    order.calculate_totals()

    return {
        "customer": customer,
        "order": order,
        "products": [product1, product2],
        "items": [item1, item2],
        "expected_subtotal": Decimal("3997.00"),
        "expected_tax": Decimal("639.52"),
        "expected_total": Decimal("4636.52"),
    }


def create_cancellation_test_scenario():
    """
    Create order ready for cancellation testing
    """
    product = ProductFactory(stock_quantity=10)
    order = OrderFactory(status=Order.PENDING)
    item = OrderItemFactory(order=order, product=product, quantity=3)

    # Reduce stock to simulate order processing
    original_stock = product.stock_quantity
    product.reduce_stock(3)

    return {
        "order": order,
        "product": product,
        "item": item,
        "original_stock": original_stock,
        "current_stock": product.stock_quantity,
        "quantity_ordered": 3,
    }


def create_notification_test_order():
    """
    Create order for notification testing
    """
    from customers.tests.factories import UserFactory

    user = UserFactory(
        first_name="Test", last_name="Customer", email="test@example.com"
    )

    customer = CustomerFactory(user=user, phone_number="+254700123456")

    product = ProductFactory(name="Notification Test Product", price=Decimal("99.99"))

    order = OrderFactory(
        customer=customer,
        delivery_address="123 Notification Test Street",
        delivery_notes="Test delivery notes",
    )

    OrderItemFactory(order=order, product=product, quantity=2)
    order.calculate_totals()

    return order


# Performance testing helpers
def create_bulk_orders(customer=None, count=10):
    """
    Create multiple orders for performance testing
    """
    if not customer:
        customer = CustomerFactory()

    orders = []
    for i in range(count):
        order = OrderFactory(
            customer=customer, delivery_address=f"Bulk Test Address {i}"
        )

        # Add 1 to 3 items per order
        for j in range(random.randint(1, 3)):
            OrderItemFactory(order=order)

        order.calculate_totals()
        order.calculate_totals()
        orders.append(order)

    return orders


# Test scenario builders
class OrderScenarioBuilder:
    """Builder for creating complex order test scenarios"""

    def __init__(self):
        self.customer = None
        self.products = []
        self.status = Order.PENDING
        self.address = "123 Default Street"
        self.items = []

    def with_customer(self, customer):
        """Set customer for order"""
        self.customer = customer
        return self

    def with_status(self, status):
        """Set order status"""
        self.status = status
        return self

    def with_address(self, address):
        """Set delivery address"""
        self.address = address
        return self

    def add_item(self, product=None, quantity=1, price=None):
        """Add item to order"""
        if not product:
            kwargs = {}
            if price:
                kwargs["price"] = Decimal(str(price))
            product = ProductFactory(**kwargs)

        self.items.append((product, quantity))
        return self

    def build(self):
        """Build the order scenario"""
        if not self.customer:
            self.customer = CustomerFactory()

        order = OrderFactory(
            customer=self.customer, status=self.status, delivery_address=self.address
        )

        created_items = []
        for product, quantity in self.items:
            item = OrderItemFactory(order=order, product=product, quantity=quantity)
            created_items.append(item)

        order.calculate_totals()

        return {
            "order": order,
            "customer": self.customer,
            "items": created_items,
            "products": [item.product for item in created_items],
        }


def create_tax_calculation_test_data():
    """Create specific data for tax calculation testing"""
    scenarios = []

    test_prices = [
        Decimal("99.99"),
        Decimal("100.00"),
        Decimal("33.33"),
        Decimal("1000.01"),
    ]

    for price in test_prices:
        product = ProductFactory(price=price)
        order = OrderFactory()
        OrderItemFactory(order=order, product=product, quantity=1)

        order.calculate_totals()

        scenarios.append(
            {
                "price": price,
                "order": order,
                "expected_subtotal": price,
                "expected_tax": price * Decimal("0.16"),
                "expected_total": price * Decimal("1.16"),
            }
        )

    return scenarios
