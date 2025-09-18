from django.urls import include, path

urlpatterns = [
    path(
        "v1/",
        include(
            [
                path("", include("products.api.urls")),
                path("", include("orders.api.urls")),
                path("", include("customers.api.urls")),
            ]
        ),
    ),
]
