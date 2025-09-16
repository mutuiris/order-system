from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
from typing import TYPE_CHECKING
from customers.models import Customer
from products.models import Product

if TYPE_CHECKING:
    from django.db.models import QuerySet


class Order(models.Model):
    """
    Order header model representing a customer's order.
    Contains order level information and status tracking.
    """
    
    # Order status choices
    PENDING = 'PENDING'
    CONFIRMED = 'CONFIRMED' 
    PROCESSING = 'PROCESSING'
    SHIPPED = 'SHIPPED'
    DELIVERED = 'DELIVERED'
    CANCELLED = 'CANCELLED'
    
    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (CONFIRMED, 'Confirmed'),
        (PROCESSING, 'Processing'),
        (SHIPPED, 'Shipped'),
        (DELIVERED, 'Delivered'),
        (CANCELLED, 'Cancelled'),
    ]
    
    # Customer who placed the order
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name='orders'
    )
    
    # Type hint
    if TYPE_CHECKING:
        items: 'QuerySet[OrderItem]'
        id: int
    
    # Order tracking
    order_number = models.CharField(
        max_length=20,
        unique=True,
        help_text="Unique order identifier for customer reference"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=PENDING
    )
    
    # Financial totals that calculates from order items
    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    tax_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Delivery information
    delivery_address = models.TextField(blank=True)
    delivery_notes = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # SMS and email notification tracking
    sms_sent = models.BooleanField(default=False)
    email_sent = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Order'
        verbose_name_plural = 'Orders'
    
    def __str__(self):
        return f"Order {self.order_number} - {self.customer.user.email}"
    
    def save(self, *args, **kwargs):
        """Generate order number if not provided"""
        if not self.order_number:
            self.order_number = self.generate_order_number()
        super().save(*args, **kwargs)
    
    def generate_order_number(self):
        """Generate unique order number"""
        import uuid
        from datetime import datetime

        date_part = datetime.now().strftime('%Y%m%d')
        unique_part = str(uuid.uuid4())[:4].upper()
        return f"ORD-{date_part}-{unique_part}"
    
    def calculate_totals(self):
        """Calculate and update order totals from line items"""
        items = self.items.all()
        
        self.subtotal = sum(item.line_total for item in items)
        
        # Tax calculation
        self.tax_amount = self.subtotal * Decimal('0.16')
        
        self.total_amount = self.subtotal + self.tax_amount
        
        # Save without triggering save() again to avoid recursion
        Order.objects.filter(pk=self.pk).update(
            subtotal=self.subtotal,
            tax_amount=self.tax_amount,
            total_amount=self.total_amount
        )
    
    @property
    def item_count(self):
        """Total number of items in this order"""
        return sum(item.quantity for item in self.items.all())
    
    @property 
    def can_be_cancelled(self):
        """Check if order can still be cancelled"""
        return self.status in [self.PENDING, self.CONFIRMED]
    
    def mark_as_confirmed(self):
        """Mark order as confirmed and trigger notifications"""
        if self.status == self.PENDING:
            self.status = self.CONFIRMED
            self.save()
            
            # TODO: Add notification system later
            # from .tasks import send_order_notifications
            # send_order_notifications.delay(self.id)
    
    def get_status_display_color(self):
        """Return CSS color class for status display"""
        status_colors = {
            self.PENDING: 'warning',
            self.CONFIRMED: 'info', 
            self.PROCESSING: 'primary',
            self.SHIPPED: 'success',
            self.DELIVERED: 'success',
            self.CANCELLED: 'danger',
        }
        return status_colors.get(self.status, 'secondary')


class OrderItem(models.Model):
    """
    Order line item model representing individual products in an order.
    Stores snapshot of product data at time of purchase.
    """
    
    # Link to order header
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items'
    )
    
    # Product information that snapshot at time of order
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='order_items'
    )
    
    # Type hints
    if TYPE_CHECKING:
        id: int
    
    # Snapshot fields that preserve data even if product changes
    product_name = models.CharField(max_length=200)
    product_sku = models.CharField(max_length=50)
    
    # Quantity ordered
    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)]
    )
    
    # Price snapshot what customer actually paid
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Price per unit at time of order"
    )
    
    # Calculated field
    line_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="quantity * unit_price"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Order Item'
        verbose_name_plural = 'Order Items'
    
    def __str__(self):
        return f"{self.quantity}x {self.product_name} (Order: {self.order.order_number})"
    
    def save(self, *args, **kwargs):
        """Auto-populate snapshot fields and calculate line total"""
        if not self.product_name and self.product:
            self.product_name = self.product.name
            self.product_sku = self.product.sku
            self.unit_price = self.product.price
        
        # Calculate line total
        self.line_total = Decimal(str(self.quantity)) * self.unit_price
        
        super().save(*args, **kwargs)
        
        # Update order totals after saving line item
        if kwargs.get('update_totals', True):
            self.order.calculate_totals()
    
    def delete(self, *args, **kwargs):
        """Update order totals after deleting line item"""
        order = self.order
        result = super().delete(*args, **kwargs)
        order.calculate_totals()
        return result
    
    @property
    def savings_amount(self):
        """Calculate savings if current product price is higher"""
        current_price = self.product.price
        if current_price > self.unit_price:
            return (current_price - self.unit_price) * self.quantity
        return Decimal('0.00')
    
    def is_in_stock(self):
        """Check if ordered quantity is still available"""
        return self.product.stock_quantity >= self.quantity