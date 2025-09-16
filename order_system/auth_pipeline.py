"""
OIDC Authentication Pipeline
Handles user creation and customer profile creation from Google OAuth2 data
"""

import logging
from customers.models import Customer

logger = logging.getLogger(__name__)


def create_customer_profile(strategy, details, user=None, *args, **kwargs):
    """
    Custom pipeline step to create a customer profile when user logs in
    Links Django user model with Customer model
    """

    if user and not hasattr(user, 'customer_profile'):
        try:
            # Extract phone number from OIDC details if available
            phone_number = details.get('phone_number', '+254700000000')

            # Create customer profile
            customer, created = Customer.objects.get_or_create(
                user=user,
                defaults={'phone_number': phone_number}
            )
            if created:
                logger.info(f"Created customer profile for user {user.email}")
            else:
                logger.debug(
                    f"Customer profile already exists for user {user.email}")

            logger.info(f"Created customer profile for user {user.email}")

        except Exception as e:
            logger.error(
                f"Failed to create customer profile for {user.email}: {str(e)}")
            pass

    return {'user': user}
