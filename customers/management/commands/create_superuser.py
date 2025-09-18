from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from customers.models import Customer
import os


class Command(BaseCommand):
    help = "Create a superuser and customer profile"

    def handle(self, *args, **options):
        username = os.environ.get("ADMIN_USERNAME", "admin")
        email = os.environ.get("ADMIN_EMAIL", "admin@example.com")
        password = os.environ.get("ADMIN_PASSWORD", "admin123")

        # Check if superuser already exists
        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f'Superuser "{username}" already exists.')
            )
            return

        # Create superuser
        user = User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
            first_name="Admin",
            last_name="User",
        )

        # Create customer profile
        Customer.objects.get_or_create(
            user=user, defaults={"phone_number": "+254700000000", "is_active": True}
        )

        self.stdout.write(
            self.style.SUCCESS(f'Successfully created superuser "{username}"')
        )
