"""
Customer models for order system
"""

from django.contrib.auth.models import User
from django.db import models


class Customer(models.Model):
    """
    Customer model for users who can place orders
    Links to Django's built-in User model
    """

    # Link to Django's User model
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="customer_profile"
    )

    # Customer contact informatiom
    phone_number = models.CharField(
        max_length=20, help_text="Phone number for SMS notifications"
    )

    # Customer preferences
    is_active = models.BooleanField(
        default=True, help_text="Checks whether this customer account is active"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Customer"
        verbose_name_plural = "Customers"

    def __str__(self):
        """String representation for debugging and admin interface"""
        return f"{self.user.get_full_name()} ({self.user.email})"

    @property
    def full_name(self):
        """Returns the full name of the customer"""
        return self.user.get_full_name() or self.user.username

    @property
    def email(self):
        """Returns the email of the customer"""
        return self.user.email
