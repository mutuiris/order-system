from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CustomerOrderStatsView, OrderViewSet

# Create router and register viewsets
router = DefaultRouter()
router.register(r"orders", OrderViewSet, basename="order")
router.register(r"stats", CustomerOrderStatsView, basename="order-stats")

urlpatterns = [
    path("", include(router.urls)),
]
