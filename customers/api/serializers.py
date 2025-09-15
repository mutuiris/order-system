from rest_framework import serializers
from django.contrib.auth.models import User
from ..models import Customer


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for User model information
    """

    class Mets:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'date_joined']
        read_only_fields = ['id', 'username', 'date_joined']


class CustomerSerializer(serializers.ModelSerializer):
    """
    Serializer for Customer model with user information
    """

    user = UserSerializer(read_only=True)
    full_name = serializers.ReadOnlyField()
    email = serializers.ReadOnlyField()

    class Meta: # type: ignore
        model = Customer
        fields = [
        'id', 'user', 'phone_number', 'full_name',
        'email', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

class CustomerUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating customer profile information
    Allows updating both user and customer fields
    """

    first_name = serializers.CharField(source='user.first_name', max_length=30)
    last_name = serializers.CharField(source='user.last_name', max_length=30)

    class Meta: # type: ignore
        model = Customer
        fields = ['phone_number', 'first_name', 'last_name']

    def update(self, instance, validated_data):
        """Update both User and Customer fields"""
        user_data = validated_data.pop('user', {})

        # Update user fields
        for attr, value in user_data.items():
            setattr(instance.user, attr, value)
        instance.user.save()

        # Update customer fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        return instance

class AuthTokenSerializer(serializers.Serializer):
    """
    Serializer for authentication token response
    Returns JWT token and user information after successful login
    """

    access_token = serializers.CharField()
    token_type = serializers.CharField(default='Bearer')
    expires_in = serializers.IntegerField()
    user = CustomerSerializer()

    def to_representation(self, instance):
        """Format authentication response"""
        return {
            'access_token': instance['access_token'],
            'token_type': instance['token_type'],
            'expires_in': instance['expires_in'],
            'user': instance['user']
        }

class AuthCallbackSerializer(serializers.Serializer):
    """
    Serializer for Google Auth callback handling
    Processes authorization code from OIDC provider
    """

    code = serializers.CharField(required=True)
    state = serializers.CharField(required=False)

    def validate_code(self, value):
        """Validate authorization code is present"""
        if not value:
            raise serializers.ValidationError("Authorization code is required")
        return value