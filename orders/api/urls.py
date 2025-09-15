from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OrderViewSet, CustomerOrderStatsView

# Create router and register viewsets
router = DefaultRouter()
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'stats', CustomerOrderStatsView, basename='order-stats')

urlpatterns = [
    path('', include(router.urls)),
]