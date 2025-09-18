"""
URL configuration for order_system project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def api_root(request):
    """Root endpoint showing available API paths"""
    return JsonResponse(
        {
            "status": "running",
            "message": "Order Processing System API",
            "version": "v1",
            "endpoints": {
                "api": "/api/v1/",
                "admin": "/admin/",
                "auth": "/auth/",
                "health": "/health/",
            },
            "documentation": "https://github.com/mutuiris/order-system",
        }
    )


def health_check(request):
    """Health check endpoint for monitoring"""
    try:
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"

    return JsonResponse(
        {
            "status": "healthy" if db_status == "healthy" else "unhealthy",
            "database": db_status,
        }
    )


urlpatterns = [
    path("", api_root, name="api-root"),
    path("health/", health_check, name="health-check"),
    path("admin/", admin.site.urls),
    path("api/", include("order_system.api_urls")),
    path("auth/", include("social_django.urls", namespace="social")),
]
