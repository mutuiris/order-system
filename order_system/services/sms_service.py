"""
SMS service for order notifications
Handles SMS sending via Africa's Talking API
"""

import logging
from django.conf import settings
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class SMSService:
    """SMS service wrapper for Africa's Talking API."""

    def __init__(self):
        self.username = settings.AFRICASTALKING_USERNAME
        self.api_key = settings.AFRICASTALKING_API_KEY
        self.sender_id = getattr(settings, 'AFRICASTALKING_SENDER_ID', None)
        self._client: Optional[Any] = None

    def _get_client(self) -> Optional[Any]:
        """Initialize Africa's Talking client."""
        if self._client is None:
            try:
                import africastalking
                africastalking.initialize(self.username, self.api_key)
                self._client = africastalking.SMS
                logger.info("SMS service initialized")
            except Exception as e:
                logger.error(f"SMS initialization failed: {str(e)}")
                return None

        return self._client

    def format_phone_number(self, phone_number: str) -> str:
        """Format phone number for Kenya"""
        clean = ''.join(c for c in phone_number if c.isdigit() or c == '+')

        if clean.startswith('+254'):
            return clean
        elif clean.startswith('254'):
            return f'+{clean}'
        elif clean.startswith('0'):
            return f'+254{clean[1:]}'
        elif len(clean) == 9 and clean[0] == '7':
            return f'+254{clean}'
        else:
            return clean if clean.startswith('+') else f'+{clean}'

    def validate_phone_number(self, phone_number: str) -> bool:
        """Validate Kenya phone number format"""
        formatted = self.format_phone_number(phone_number)
        return formatted.startswith('+2547') and len(formatted) == 13

    def send_sms(self, phone_number: str, message: str) -> Dict[str, Any]:
        """Send SMS to single recipient"""
        if not phone_number or not message.strip():
            return {'success': False, 'error': 'Phone number and message required'}

        formatted_number = self.format_phone_number(phone_number)
        if not self.validate_phone_number(phone_number):
            return {'success': False, 'error': 'Invalid phone number format'}

        client = self._get_client()
        if not client:
            return {'success': False, 'error': 'SMS service not available'}

        try:
            assert client is not None, "SMS client should be available"

            response = client.send(
                message=message,
                recipients=[formatted_number],
                sender_id=self.sender_id
            )

            logger.info(f"SMS sent to {formatted_number}")
            return {'success': True, 'response': response}

        except Exception as e:
            logger.error(f"SMS sending failed: {str(e)}")
            return {'success': False, 'error': str(e)}


# Global instance
sms_service = SMSService()
