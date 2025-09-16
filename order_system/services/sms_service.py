"""
SMS Service using Africa's Talking API
Handles sending SMS notifications for order updates
"""

import logging
from django.conf import settings
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class SMSService:
    """
    SMS service wrapper for Africa's Talking API
    """

    def __init__(self):
        """Initialize the SMS service with API credentials"""
        self.username = settings.AFRICASTALKING_USERNAME
        self.api_key = settings.AFRICASTALKING_API_KEY
        self.sender_id = settings.AFRICASTALKING_SENDER_ID

        # Validate configuration
        if not self.api_key:
            logger.error("Africa's Talking API key is not configured.")
            raise ValueError("Africa's Talking API key is required.")

        self._sms_client: Optional[Any] = None
        self._client_initialized = False

    def _get_client(self) -> Optional[Any]:
        """
        Lazy load of Africa's Talking client with proper error handling
        """
        if not self._client_initialized:
            try:
                import africastalking

                # Initialize Africa's Talking
                africastalking.initialize(self.username, self.api_key)
                self._sms_client = africastalking.SMS
                self._client_initialized = True

                logger.info(
                    "Africa's Talking SMS service initialized successfully")

            except ImportError:
                logger.error(
                    "Africa's Talking library is not installed. Install with: pip install africastalking")
                self._sms_client = None
                self._client_initialized = True
            except Exception as e:
                logger.error(
                    f"Failed to initialize Africa's Talking: {str(e)}")
                self._sms_client = None
                self._client_initialized = True

        return self._sms_client

    def _is_service_available(self) -> bool:
        """Check if SMS service is properly configured and available"""
        return self._get_client() is not None

    def format_phone_number(self, phone_number: str) -> str:
        """
        Format phone number for Kenya (+254 format)
        """
        # Remove all non-digit characters except +
        clean_number = ''.join(
            c for c in phone_number if c.isdigit() or c == '+')

        if clean_number.startswith('+254'):
            return clean_number
        elif clean_number.startswith('254'):
            return f'+{clean_number}'
        elif clean_number.startswith('0'):
            return f'+254{clean_number[1:]}'
        elif len(clean_number) == 9 and clean_number[0] == '7':
            return f'+254{clean_number}'
        else:
            return clean_number if clean_number.startswith('+') else f'+{clean_number}'

    def validate_phone_number(self, phone_number: str) -> bool:
        """
        Validate Kenyan phone numbers
        """
        formatted_number = self.format_phone_number(phone_number)
        return formatted_number.startswith('+2547') and len(formatted_number) == 13

    def send_sms(self, phone_number: str, message: str) -> Dict[str, Any]:
        """
        Send SMS to a single recipient

        Args:
            phone_number: Recipient's phone number
            message: SMS message content

        Returns:
            Dict with success status and details
        """
        return self.send_bulk_sms([phone_number], message)

    def send_bulk_sms(self, phone_numbers: List[str], message: str) -> Dict[str, Any]:
        """
        Send SMS to multiple recipients

        Args:
            phone_numbers: List of recipient phone numbers
            message: SMS message content

        Returns:
            Dict with success status and details
        """
        # Input validation
        if not phone_numbers:
            return {
                'success': False,
                'error': 'No phone numbers provided',
                'results': []
            }

        if not message.strip():
            return {
                'success': False,
                'error': 'Message content is empty',
                'results': []
            }

        # Check if service is available
        if not self._is_service_available():
            error_msg = "SMS service is not available. Check your Africa's Talking configuration."
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'sent_to': [],
                'invalid_numbers': phone_numbers,
                'results': []
            }

        # Format and validate phone numbers
        formatted_numbers = []
        invalid_numbers = []

        for number in phone_numbers:
            formatted = self.format_phone_number(number)
            if self.validate_phone_number(number):
                formatted_numbers.append(formatted)
            else:
                invalid_numbers.append(number)
                logger.warning(f"Invalid phone number: {number}")

        if not formatted_numbers:
            return {
                'success': False,
                'error': 'No valid phone numbers provided',
                'invalid_numbers': invalid_numbers,
                'results': []
            }

        try:
            # Get SMS client
            sms_client = self._get_client()
            assert sms_client is not None, "SMS client should be available"

            # Send SMS via Africa's Talking
            response = sms_client.send(
                message=message,
                recipients=formatted_numbers,
                sender_id=self.sender_id if self.sender_id else None
            )

            logger.info(f"SMS sent to {len(formatted_numbers)} recipients")
            logger.debug(f"SMS response: {response}")

            return {
                'success': True,
                'message': f'SMS sent to {len(formatted_numbers)} recipients',
                'sent_to': formatted_numbers,
                'invalid_numbers': invalid_numbers,
                'response': response,
                'results': response.get('SMSMessageData', {}).get('Recipients', [])
            }

        except Exception as e:
            error_msg = f"Failed to send SMS: {str(e)}"
            logger.error(error_msg, exc_info=True)

            return {
                'success': False,
                'error': error_msg,
                'sent_to': [],
                'invalid_numbers': invalid_numbers + formatted_numbers,
                'results': []
            }

    def get_delivery_reports(self) -> Dict[str, Any]:
        """
        Fetch delivery reports from Africa's Talking

        Checks if SMS messages were delivered successfully
        """
        if not self._is_service_available():
            error_msg = "SMS service is not available. Check your Africa's Talking configuration."
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'reports': []
            }

        try:
            sms_client = self._get_client()
            assert sms_client is not None, "SMS client should be available"

            response = sms_client.fetch_messages()

            return {
                'success': True,
                'reports': response.get('SMSMessageData', {}).get('Messages', [])
            }

        except Exception as e:
            error_msg = f"Failed to fetch delivery reports: {str(e)}"
            logger.error(error_msg, exc_info=True)

            return {
                'success': False,
                'error': error_msg,
                'reports': []
            }

    def get_service_status(self) -> Dict[str, Any]:
        """
        Get the current status of the SMS service

        Returns:
            Dict with service availability and configuration status
        """
        return {
            'available': self._is_service_available(),
            'configured': bool(self.api_key and self.username),
            'username': self.username,
            'sender_id': self.sender_id,
            'api_key_set': bool(self.api_key)
        }


#  Singleton instance
sms_service = SMSService()
