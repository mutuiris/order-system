from django.db import transaction
from django.db.models import Sum
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from ..models import Order, OrderItem
from .serializers import (
    OrderCreateSerializer,
    OrderDetailSerializer,
    OrderListSerializer,
    OrderUpdateSerializer,
)


class OrderViewSet(viewsets.ModelViewSet):
    """
    ViewSet for orders with customer access control
    Provides full CRUD operations with proper authorization
    """

    permission_classes = [permissions.IsAuthenticated]

    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["status"]
    ordering_fields = ["created_at", "total_amount"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """
        Filter orders to only show current user orders
        """
        try:
            customer_profile = getattr(self.request.user, "customer_profile", None)
            if not customer_profile:
                return Order.objects.none()

            return (
                Order.objects.filter(customer=customer_profile)
                .select_related("customer__user")
                .prefetch_related("items__product")
            )
        except AttributeError:
            return Order.objects.none()

    def get_serializer_class(self):
        """Use different serializers for different actions"""
        if self.action == "list":
            return OrderListSerializer
        elif self.action == "create":
            return OrderCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return OrderUpdateSerializer
        return OrderDetailSerializer

    def create(self, request, *args, **kwargs):
        """
        Create a new order
        Returns detailed order information after successful creation
        """
        # Check if user has customer profile
        if not hasattr(request.user, "customer_profile"):
            return Response(
                {"error": "Customer profile required to place orders"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            try:
                order = serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            except Exception as e:
                # Log the actual error for debugging
                import logging

                logger = logging.getLogger(__name__)
                logger.error(f"Order creation failed: {str(e)}", exc_info=True)
                return Response(
                    {"error": "Order creation failed. Please try again."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        """
        Update order with business rule validation
        """
        instance = self.get_object()

        # Check if order can be updated
        if instance.status in [Order.DELIVERED, Order.CANCELLED]:
            return Response(
                {"error": "Cannot update completed or cancelled orders"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return super().update(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """
        Cancel an order if it is in a cancellable state
        Uses database transactions to ensure data consistency
        """
        try:
            with transaction.atomic():
                order = Order.objects.select_for_update().get(pk=pk)

                # Verify user owns this order
                customer_profile = getattr(self.request.user, "customer_profile", None)
                if not customer_profile or order.customer != customer_profile:
                    return Response(
                        {"error": "Order not found or access denied"},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                # Check if order can be cancelled
                if not order.can_be_cancelled:
                    return Response(
                        {"error": f"Cannot cancel order in {order.status} status"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                order_items = order.items.select_related("product").select_for_update(
                    of=("product",)
                )

                for item in order_items:
                    product = item.product
                    product.stock_quantity += item.quantity
                    product.save(update_fields=["stock_quantity"])

                # Update order status
                order.status = Order.CANCELLED
                order.save(update_fields=["status", "updated_at"])

                # Serialize the updated order
                serializer = OrderDetailSerializer(order, context={"request": request})

                return Response(
                    {
                        "message": "Order cancelled successfully",
                        "order": serializer.data,
                    }
                )

        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(
                f"Order cancellation failed for order {pk}: {str(e)}", exc_info=True
            )

            return Response(
                {"error": "Order cancellation failed. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """
        Get order summary statistics for the current user
        """
        queryset = self.get_queryset()

        from decimal import Decimal

        # Initialize with all expected types
        summary = {
            "total_orders": queryset.count(),
            "pending_orders": queryset.filter(status=Order.PENDING).count(),
            "completed_orders": queryset.filter(status=Order.DELIVERED).count(),
            "cancelled_orders": queryset.filter(status=Order.CANCELLED).count(),
            "total_spent": Decimal("0.00"),
            "recent_orders": [],
        }

        # Only count delivered orders as spent
        total_spent = queryset.filter(status=Order.DELIVERED).aggregate(
            total=Sum("total_amount")
        )["total"] or Decimal("0.00")
        summary["total_spent"] = total_spent

        # Add recent orders
        recent_orders = queryset[:5]
        summary["recent_orders"] = OrderListSerializer(
            recent_orders, many=True, context={"request": request}
        ).data

        return Response(summary)

    @action(detail=True, methods=["get"])
    def track(self, request, pk=None):
        """
        Get order tracking information
        """
        order = self.get_object()

        # Build status timeline
        status_timeline = []

        if order.status != Order.CANCELLED:
            status_timeline.append(
                {
                    "status": "PENDING",
                    "completed": True,
                    "date": order.created_at,
                    "description": "Order placed",
                }
            )

            if order.status in [
                Order.CONFIRMED,
                Order.PROCESSING,
                Order.SHIPPED,
                Order.DELIVERED,
            ]:
                status_timeline.append(
                    {
                        "status": "CONFIRMED",
                        "completed": True,
                        "date": order.updated_at,
                        "description": "Order confirmed",
                    }
                )

            if order.status in [Order.PROCESSING, Order.SHIPPED, Order.DELIVERED]:
                status_timeline.append(
                    {
                        "status": "PROCESSING",
                        "completed": order.status != Order.PROCESSING,
                        "date": (
                            order.updated_at
                            if order.status != Order.PROCESSING
                            else None
                        ),
                        "description": "Order being prepared",
                    }
                )

            if order.status in [Order.SHIPPED, Order.DELIVERED]:
                status_timeline.append(
                    {
                        "status": "SHIPPED",
                        "completed": order.status == Order.DELIVERED,
                        "date": (
                            order.updated_at if order.status != Order.SHIPPED else None
                        ),
                        "description": "Order shipped",
                    }
                )

            if order.status == Order.DELIVERED:
                status_timeline.append(
                    {
                        "status": "DELIVERED",
                        "completed": True,
                        "date": order.updated_at,
                        "description": "Order delivered",
                    }
                )

        return Response(
            {
                "order_number": order.order_number,
                "current_status": order.status,
                "timeline": status_timeline,
                "estimated_delivery": None,
                "tracking_notes": order.delivery_notes,
            }
        )


class CustomerOrderStatsView(viewsets.GenericViewSet):
    """
    ViewSet for customer order statistics and analytics
    """

    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=["get"])
    def monthly_spending(self, request):
        """
        Get monthly spending statistics for the current user.
        Useful for spending analysis and budgeting features.
        """
        if not hasattr(request.user, "customer_profile"):
            return Response(
                {"error": "Customer profile required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from datetime import datetime, timedelta

        from django.db.models import Sum
        from django.utils import timezone

        twelve_months_ago = timezone.now() - timedelta(days=365)
        orders = Order.objects.filter(
            customer=request.user.customer_profile,
            created_at__gte=twelve_months_ago,
            status__in=[
                Order.CONFIRMED,
                Order.PROCESSING,
                Order.SHIPPED,
                Order.DELIVERED,
            ],
        )

        # Group by month and calculate totals
        monthly_data = []
        current_date = timezone.now().replace(day=1)

        for i in range(12):
            month_start = current_date.replace(month=current_date.month - i)
            if i == 11:
                month_end = current_date.replace(month=current_date.month - i + 1)
            else:
                month_end = current_date.replace(month=current_date.month - i + 1)

            month_orders = orders.filter(
                created_at__gte=month_start, created_at__lt=month_end
            )

            total_spent = (
                month_orders.aggregate(total=Sum("total_amount"))["total"] or 0
            )

            monthly_data.append(
                {
                    "month": month_start.strftime("%B %Y"),
                    "total_spent": total_spent,
                    "order_count": month_orders.count(),
                }
            )

        return Response(
            {
                "monthly_spending": list(reversed(monthly_data)),
                "total_orders": orders.count(),
                "total_spent": orders.aggregate(total=Sum("total_amount"))["total"]
                or 0,
            }
        )
