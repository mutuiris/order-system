"""
SMS test command.
"""

from django.core.management.base import BaseCommand
from order_system.services.sms_service import sms_service


class Command(BaseCommand):
    help = 'Test SMS functionality'

    def add_arguments(self, parser):
        """
        Add command-line arguments for testing the SMS service.
        
        Adds a required positional `phone_number`, an optional positional `message` (defaults to
        'Hello from Order System!'), and a `--validate-only` flag to validate the number without sending.
        """
        parser.add_argument('phone_number', type=str, help='Phone number to send SMS to')
        parser.add_argument(
            'message', 
            type=str, 
            nargs='?', 
            default='Hello from Order System!',
            help='Message to send'
        )
        parser.add_argument(
            '--validate-only',
            action='store_true',
            help='Only validate phone number'
        )

    def handle(self, *args, **options):
        """
        Execute the management command to test SMS functionality: format and validate a phone number, optionally send an SMS, and print status to stdout.
        
        This reads the following keys from `options`:
        - `phone_number` (str): recipient number to format/validate/send to.
        - `message` (str): text to send (default provided by the command).
        - `validate_only` (bool): if true, only perform validation and exit.
        
        Behavior:
        - Writes progress and results to stdout.
        - Uses `sms_service.format_phone_number` and `sms_service.validate_phone_number` to format and validate the provided number.
        - If validation fails, prints an error and returns early.
        - If `validate_only` is true and validation passed, prints success and returns early.
        - Otherwise calls `sms_service.send_sms(formatted_number, message)` and prints success or the error returned in the result.
        
        Returns:
            None
        """
        phone_number = options['phone_number']
        message = options['message']
        validate_only = options['validate_only']
        
        self.stdout.write('Testing SMS service...')
        
        # Format and validate
        formatted_number = sms_service.format_phone_number(phone_number)
        is_valid = sms_service.validate_phone_number(phone_number)
        
        self.stdout.write(f'Phone: {phone_number} -> {formatted_number}')
        self.stdout.write(f'Valid: {is_valid}')
        
        if not is_valid:
            self.stdout.write(self.style.ERROR('Invalid phone number'))
            return
        
        if validate_only:
            self.stdout.write(self.style.SUCCESS('Validation passed'))
            return
        
        # Send SMS
        self.stdout.write(f'Sending: "{message}"')
        result = sms_service.send_sms(formatted_number, message)
        
        if result['success']:
            self.stdout.write(self.style.SUCCESS('SMS sent successfully!'))
        else:
            self.stdout.write(self.style.ERROR(f'Failed: {result.get("error")}'))