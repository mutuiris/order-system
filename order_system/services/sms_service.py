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
        """
        Initialize the SMSService by loading Africa's Talking credentials and preparing the client cache.
        
        Reads AFRICASTALKING_USERNAME and AFRICASTALKING_API_KEY from Django settings, optionally reads AFRICASTALKING_SENDER_ID if present, and sets an internal _client cache to None for lazy initialization.
        """
        self.username = settings.AFRICASTALKING_USERNAME
        self.api_key = settings.AFRICASTALKING_API_KEY
        self.sender_id = getattr(settings, 'AFRICASTALKING_SENDER_ID', None)
        self._client: Optional[Any] = None

    def _get_client(self) -> Optional[Any]:
        """
        Lazily initialize and return the Africa's Talking SMS client.
        
        On first call this dynamically imports and initializes the `africastalking` SDK using
        the service credentials stored on the instance, caches the SMS client, and returns it.
        Subsequent calls return the cached client. If initialization fails, logs the error and
        returns None.
        """
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
        """
        Normalize a phone number into a Kenyan international format (+254...).
        
        This function strips all characters except digits and a leading '+' then normalizes common Kenyan phone formats:
        - If already starts with '+254' it is returned unchanged.
        - If starts with '254' it is prefixed with '+'.
        - If starts with '0' it is converted to '+254' followed by the remaining digits (e.g. '0712...' -> '+254712...').
        - If it is 9 digits and starts with '7' it is treated as a local mobile number and converted to '+254' + digits.
        - For any other digits-only input, a leading '+' is added if missing.
        
        Parameters:
            phone_number (str): Input phone number in any common format (may include spaces, dashes, or other punctuation).
        
        Returns:
            str: Phone number normalized to an international format, usually starting with '+254'.
        """
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
        """
        Return True if the given phone number is a valid Kenyan mobile number in international format.
        
        The input is first normalized with format_phone_number. Returns True when the normalized number starts with "+2547" and has a total length of 13 characters (e.g. "+254712345678"); otherwise returns False.
        """
        formatted = self.format_phone_number(phone_number)
        return formatted.startswith('+2547') and len(formatted) == 13

    def send_sms(self, phone_number: str, message: str) -> Dict[str, Any]:
        """
        Send an SMS to a single recipient using the configured Africa's Talking client.
        
        The provided phone number is normalized with format_phone_number and validated with validate_phone_number before sending.
        If sending succeeds, the function returns a structured dict containing the raw API response, per-recipient results, and any extracted message IDs.
        If validation fails or the SMS client cannot be initialized, returns an error-shaped dict.
        
        Parameters:
            phone_number (str): Recipient phone number in any common Kenyan format (e.g. starting with 0, 7, 254, or +254); will be normalized.
            message (str): Message body (must be non-empty after trimming).
        
        Returns:
            Dict[str, Any]: A result dictionary. On success:
                {
                    'success': True,
                    'message': str,           # human-readable summary
                    'sent_to': [str],         # list of formatted recipient numbers
                    'invalid_numbers': [],    # list of numbers considered invalid (always empty for single-recipient flow)
                    'response': dict,         # raw API response from Africa's Talking
                    'results': list,          # per-recipient result objects from the API
                    'message_ids': list       # extracted records for recipients with status 'Success'
                }
            On failure:
                {'success': False, 'error': str}  # error contains a brief description of the failure
        """
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
            logger.debug(f"SMS response: {response}")

            # Extract message IDs for tracking
            recipients_data = response.get(
                'SMSMessageData', {}).get('Recipients', [])
            message_ids = []

            for recipient in recipients_data:
                if recipient.get('status') == 'Success':
                    message_ids.append({
                        'phone': recipient.get('number'),
                        'message_id': recipient.get('messageId'),
                        'status': recipient.get('status'),
                        'cost': recipient.get('cost')
                    })

            return {
                'success': True,
                'message': f'SMS sent to 1 recipients',
                'sent_to': [formatted_number],
                'invalid_numbers': [],
                'response': response,
                'results': recipients_data,
                'message_ids': message_ids
            }

        except Exception as e:
            logger.error(f"SMS sending failed: {str(e)}")
            return {'success': False, 'error': str(e)}


# Global instance
sms_service = SMSService()
