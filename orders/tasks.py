"""
Background tasks for order notifications
Handles SMS and email notifications when orders are placed
"""

import logging
from typing import TYPE_CHECKING, Any, Dict

from celery import shared_task
from django.conf import settings

# from django.core.mail import send_mail
from django.core import mail

if TYPE_CHECKING:
    from celery.result import AsyncResult

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_order_sms(self, order_id: int) -> Dict[str, Any]:
    """Send SMS notification to customer when order is placed."""
    try:
        from order_system.services.sms_service import sms_service

        from .models import Order

        order = Order.objects.select_related("customer__user").get(id=order_id)

        message = (
            f"Order confirmed! #{order.order_number}\n"
            f"Total: KES {order.total_amount}\n"
            f"Items: {order.item_count}\n"
            f"Thank you for shopping with us!"
        )

        result = sms_service.send_sms(order.customer.phone_number, message)

        if result["success"]:
            Order.objects.filter(id=order_id).update(sms_sent=True)
            logger.info(f"SMS sent for order {order.order_number}")
            return {
                "success": True,
                "order_number": order.order_number,
                "phone_number": order.customer.phone_number,
                "message": "SMS sent successfully",
            }
        else:
            logger.error(
                f"SMS failed for order {order.order_number}: {result.get('error')}"
            )
            raise Exception(f"SMS sending failed: {result.get('error')}")

    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found for SMS notification")
        return {"success": False, "error": "Order not found"}

    except Exception as e:
        logger.error(f"SMS task failed for order {order_id}: {str(e)}")

        if self.request.retries < self.max_retries:
            delay = 60 * (2**self.request.retries)
            logger.info(
                f"Retrying SMS task in {delay} seconds (attempt {self.request.retries + 1})"
            )
            raise self.retry(countdown=delay, exc=e)

        logger.error(f"SMS task failed permanently for order {order_id}")
        return {"success": False, "error": str(e)}


@shared_task(bind=True, max_retries=3)
def send_admin_email(self, order_id):
    """Send email notification to admin when order is placed."""
    try:
        from .models import Order

        order = (
            Order.objects.select_related("customer__user")
            .prefetch_related("items")
            .get(id=order_id)
        )

        subject = f"New Order: #{order.order_number} - KES {order.total_amount}"

        message = f"""
New Order Received

Customer: {order.customer.full_name} ({order.customer.email})
Phone: {order.customer.phone_number}

Order: {order.order_number}
Total: KES {order.total_amount}
Items: {order.item_count}

Address: {order.delivery_address or 'Not provided'}
Notes: {order.delivery_notes or 'None'}
"""

        email_sent = mail.send_mail(
            subject=subject,
            message=message,
            from_email=settings.EMAIL_HOST_USER or "noreply@order-system.com",
            recipient_list=[getattr(settings, "ADMIN_EMAIL", "admin@order-system.com")],
            fail_silently=False,
        )

        if email_sent:
            Order.objects.filter(id=order_id).update(email_sent=True)
            logger.info(f"Admin email sent for order {order.order_number}")
            return {"success": True, "order_number": order.order_number}
        else:
            raise Exception("Email sending returned False")

    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found for admin email")
        return {"success": False, "error": "Order not found"}

    except Exception as e:
        logger.error(f"Email task failed for order {order_id}: {str(e)}")
        raise


@shared_task
def send_order_notifications(order_id: int) -> Dict[str, Any]:
    """Send both SMS and email notifications for new order."""
    logger.info(f"Starting notification tasks for order {order_id}")

    try:
        from .models import Order

        order = Order.objects.get(id=order_id)

        if TYPE_CHECKING:
            sms_task: "AsyncResult" = send_order_sms.delay(order_id)
            email_task: "AsyncResult" = send_admin_email.delay(order_id)
        else:
            sms_task = send_order_sms.delay(order_id)
            email_task = send_admin_email.delay(order_id)

        return {
            "order_id": order_id,
            "order_number": order.order_number,
            "sms_task_id": sms_task.id,
            "email_task_id": email_task.id,
            "message": "Notification tasks started successfully",
        }

    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found for notifications")
        return {
            "order_id": order_id,
            "error": "Order not found",
            "message": "Notification tasks failed to start",
        }
    except Exception as e:
        logger.error(
            f"Failed to start notification tasks for order {order_id}: {str(e)}"
        )
        return {
            "order_id": order_id,
            "error": str(e),
            "message": "Notification tasks failed to start",
        }


@shared_task
def debug_task():
    """Debug task for testing Celery connectivity"""
    return "Celery is working"
