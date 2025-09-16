"""
Background tasks for order processing
Handles SMS and email notifications asynchronously
"""

import logging
from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

from .models import Order

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_order_sms(self, order_id):
    """
    Send SMS notification to customer when order is placed
    """
    try:
        from order_system.services.sms_service import sms_service

        # Get order details
        order = Order.objects.select_related('customer__user').get(id=order_id)

        # Format SMS message
        message = (
            f"Order confirmed! #{order.order_number}\n"
            f"Total: KES {order.total_amount:.2f}\n"
            f"Items: {order.items.count()}\n"
            f"Thank you for shopping with us"
        )

        # Send SMS
        result = sms_service.send_sms(order.customer.phone_number, message)

        if result['success']:
            # Mark SMS as sent in order
            Order.objects.filter(id=order_id).update(sms_sent=True)

            logger.info(f"SMS sent for order {order.order_number} to {order.customer.phone_number}")
            return {
                'success': True,
                'order_number': order.order_number,
                'phone_number': order.customer.phone_number,
                'message': 'SMS sent successfully'
            }
        else:
            logger.error(f"SMS failed for order {order.order_number}: {result.get('error')}")

            # Retry sending SMS
            raise Exception(f"SMS sending failed: {result.get('error')}")

    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found for SMS notification")
        return {'success': False, 'error': 'Order not found'}

    except Exception as e:
        logger.error(f"SMS task failed for order {order_id}: {str(e)}")

        # Retry with backoff
        if self.request.retries < self.max_retries:
            delay = 60 * (2 ** self.request.retries)  # Exponential backoff
            logger.info(f"Retrying SMS task in {delay} seconds (attempt {self.request.retries + 1})")
            raise self.retry(countdown=delay, exc=e)
        
        logger.error(f"SMS task failed permanently for order {order_id}")
        return {'success': False, 'error': str(e)}

@shared_task(bind=True, max_retries=3)
def send_admin_email(self, order_id):
    """
    Send email notification to admin when order is placed
    """
    try:
        # Get order with related data
        order = Order.objects.select_related(
            'customer_user'
        ).prefetch_related(
            'items__product__ategory'
        ).get(id=order_id)

        # Prepare email content
        subject = f"New Order: #{order.order_number} - KES {order.total_amount:.2f}"

        # Create context for email template
        context = {
            'order': order,
            'customer': order.customer,
            'items': order.items.all(),
            'timestamp': timezone.now(),
        }

        # Render email body from template
        try:
            html_message = render_to_string('emails/admin_order_notification.html', context)
            plain_message = render_to_string('emails/admin_order_notification.txt', context)
        except Exception:
            plain_message = f"""

Customer: {order.customer.full_name} ({order.customer.email})
Phone: {order.customer.phone_number}

Order Details:
- Total Amount: KES {order.total_amount}
- Items: {order.item_count}
- Status: {order.status}

Items Ordered:
"""
            for item in order.items.all():
                plain_message += f"  - {item.quantity} x {item.product_name} @ KES {item.unit_price} each\n"

            plain_message += f"\nDelivery Address:\n{order.delivery_address or 'Not provided'}"
            plain_message += f"\nDelivery Notes:\n{order.delivery_notes or 'None'}"
            plain_message += f"\nOrder placed at: {order.created_at}"

            html_message = None

        admin_email = getattr(settings, 'ADMIN_EMAIL', '')
        if not admin_email:
            logger.error("ADMIN_EMAIL not configured in settings")
            return {'success': False, 'error': 'Admin email not configured'}

        if isinstance(admin_email, str):
            recipient_list = [admin_email]
        elif isinstance(admin_email, (list, tuple)):
            recipient_list = list(admin_email)
        else:
            logger.error(f"Invalid ADMIN_EMAIL format: {type(admin_email)}")
            return {'success': False, 'error': 'Invalid admin email configuration'}

        # Send email
        email_sent = send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=False
        )

        if email_sent:
            # Mark email as sent in order
            Order.objects.filter(id=order_id).update(email_sent=True)

            logger.info(f"Admin email sent successfully for order {order.order_number}")
            return {
                'success': True,
                'order_number': order.order_number,
                'recipient': recipient_list[0],
                'message': 'Admin email sent successfully'
            }
        else:
            raise Exception("Email sending returned False")

    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found for admin email")
        return {'success': False, 'error': 'Order not found'}

    except Exception as e:
        logger.error(f"Admin email task failed for order {order_id}: {str(e)}")

        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            delay = 60 * (2 ** self.request.retries)
            logger.info(f"Retrying email task in {delay} secons (attempt {self.request.retries + 1})")
            raise self.retry(countdown=delay, exc=e)

        # Final failure
        logger.error(f"Admin email task failed permanently for order {order_id}")
        return {'success': False, 'error': str(e)}

@shared_task
def send_order_notifications(order_id):
    """
    Arrange all notifications for a new order
    Triggers both SMS and email notifications parallel
    """
    logger.info(f"Starting notification tasks for order {order_id}")

    try:
        # Verify order exists before starting tasks
        order = Order.objects.get(id=order_id)
        
        # Trigger SMS and email tasks in parallel
        sms_task = send_order_sms.delay(order_id)
        email_task = send_admin_email.delay(order_id)

        return {
            'order_id': order_id,
            'order_number': order.order_number,
            'sms_task_id': sms_task.id,
            'email_task_id': email_task.id,
            'message': 'Notification tasks started successfully',
        }
        
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found for notifications")
        return {
            'order_id': order_id,
            'error': 'Order not found',
            'message': 'Notification tasks failed to start'
        }
    except Exception as e:
        logger.error(f"Failed to start notification tasks for order {order_id}: {str(e)}")
        return {
            'order_id': order_id,
            'error': str(e),
            'message': 'Notification tasks failed to start'
        }