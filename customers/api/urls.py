from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CustomerViewSet
from .import views


# Create router for viewsets
router = DefaultRouter()
router.register(r'customer', CustomerViewSet, basename='customer')

urlpatterns = [
    # ViewSet URLs
    path('', include(router.urls)),

    # Authentication endpoints
    path('auth/login/', views.auth_login, name='auth-login'),
    path('auth/callback/', views.auth_callback, name='auth-callback'),
    path('auth/success/', views.auth_success, name='auth-success'),
    path('auth/logout/', views.auth_logout, name='auth-logout'),
    path('auth/status/', views.auth_status, name='auth-status'),
]
