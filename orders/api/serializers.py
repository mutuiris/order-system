from django.db import transaction
from rest_framework import serializers

from products.api.serializers import ProductListSerializer

from ..models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    """
    Serializer for order items with product information
    Used for displaying order details
    """

    product_detail = ProductListSerializer(source='product', read_only=True)
    saving_amount = serializers.ReadOnlyField()

    class Meta:  # type: ignore
        model = OrderItem
        fields = [
            'id', 'product', 'product_detail', 'product_name',
            'product_sku', 'quantity', 'unit_price', 'line_total',
            'saving_amount', 'created_at'
        ]
        read_only_fields = [
            'id', 'product_name', 'product_sku', 'unit_price',
            'line_total', 'created_at'
        ]


class OrderItemCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating order items
    """

    class Meta:  # type: ignore
        model = OrderItem
        fields = ['product', 'quantity']

    def validate_quantity(self, value):
        """Validate quantity is positive"""
        if value < 1:
            raise serializers.ValidationError("Quantity must be at least 1")
        return value

    def validate_product(self, value):
        """Validate product is active and in stock"""
        if not value.is_active:
            raise serializers.ValidationError("Product is not available")
        if not value.is_in_stock:
            raise serializers.ValidationError("Product is out of stock")
        return value

    def validate(self, attrs):
        """Validate stock availability for requested quantity"""
        product = attrs['product']
        quantity = attrs['quantity']

        if product.stock_quantity < quantity:
            raise serializers.ValidationError(
                f"Only {product.stock_quantity} units of {product.name} are available"
            )

        return attrs


class OrderListSerializer(serializers.ModelSerializer):
    """
    Serializer for order list view
    """

    customer_email = serializers.CharField(
        source='customer.user.email', read_only=True)
    item_count = serializers.ReadOnlyField()
    status_color = serializers.CharField(
        source='get_status_display_color', read_only=True)
    can_be_cancelled = serializers.ReadOnlyField()

    class Meta:  # type: ignore
        model = Order
        fields = [
            'id', 'order_number', 'customer_email',
            'status', 'status_color', 'item_count', 'total_amount',
            'can_be_cancelled', 'created_at'
        ]


class OrderDetailSerializer(serializers.ModelSerializer):
    """
    Detailed order serializer with complete order information
    """
    items = OrderItemSerializer(many=True, read_only=True)
    customer_email = serializers.CharField(
        source='customer.user.email', read_only=True)
    customer_name = serializers.CharField(
        source='customer.full_name', read_only=True)
    status_display = serializers.CharField(
        source='get_status_display', read_only=True)
    status_display_color = serializers.CharField(
        source='get_status_display_color', read_only=True)
    can_be_cancelled = serializers.ReadOnlyField()

    class Meta:  # type: ignore
        model = Order
        fields = [
            'id', 'order_number', 'customer_email', 'customer_name',
            'status', 'status_display', 'status_display_color',
            'subtotal', 'tax_amount', 'total_amount',
            'delivery_address', 'delivery_notes',
            'can_be_cancelled', 'items',
            'sms_sent', 'email_sent',
            'created_at', 'updated_at'
        ]


class OrderCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new orders
    Handle order creation with items in a single transaction
    """

    items = OrderItemCreateSerializer(many=True, write_only=True)

    class Meta:  # type: ignore
        model = Order
        fields = [
            'delivery_address', 'delivery_notes', 'items'
        ]

    def validate_items(self, value):
        """Validate order has at least one item"""
        if not value:
            raise serializers.ValidationError(
                "Order must have at least one item")

        if len(value) > 20:
            raise serializers.ValidationError(
                "Order cannot have more than 20 items")

        return value

    def create(self, validated_data):
        """
        Create order with items in a single database transaction
        """
        items_data = validated_data.pop('items')

        # Get customer from request context
        request = self.context['request']
        customer = request.user.customer_profile

        with transaction.atomic():
            # Create the order
            order = Order.objects.create(
                customer=customer,
                **validated_data
            )

            # Create order items
            for item_data in items_data:
                product = item_data['product']
                quantity = item_data['quantity']

                # Double check stock availability within transaction
                if product.stock_quantity < quantity:
                    raise serializers.ValidationError(
                        f"Insufficient stock for {product.name}"
                    )

                # Create order item
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=quantity,
                )

                # Reduce product stock
                product.reduce_stock(quantity)

            # Mark order as confirmed to trigger notifications
            order.mark_as_confirmed()

            return order

    def to_representation(self, instance):
        """Return detailed order data after creation"""
        return OrderDetailSerializer(instance, context=self.context).data


class OrderUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating order status and delivery information
    """

    class Meta:  # type: ignore
        model = Order
        fields = ['status', 'delivery_address', 'delivery_notes']

    def validate_status(self, value):
        """Validate status transitions"""
        if self.instance and isinstance(self.instance, Order):
            current_status = self.instance.status

            # Allowed status transitions definitions
            allowed_transitions = {
                Order.PENDING: [Order.CONFIRMED, Order.CANCELLED],
                Order.CONFIRMED: [Order.PROCESSING, Order.CANCELLED],
                Order.PROCESSING: [Order.SHIPPED],
                Order.SHIPPED: [Order.DELIVERED],
                Order.DELIVERED: [],
                Order.CANCELLED: [],
            }

            if value not in allowed_transitions.get(current_status, []):
                raise serializers.ValidationError(
                    f"Cannot change status from {current_status} to {value}"
                )

            return value
