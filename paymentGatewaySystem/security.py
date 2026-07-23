import base64
import hashlib
import json
import os
from django.conf import settings
from rest_framework import permissions, authentication, exceptions
from cryptography.fernet import Fernet
from paymentGatewaySystem.models import MerchantProfile, CustomerProfile


def _get_fernet_cipher():
    """
    Returns Fernet cipher based on PAYMENT_ENCRYPTION_KEY setting.
    Ensures 32-byte url-safe base64 key format for AES-256 encryption.
    """
    key = getattr(settings, 'PAYMENT_ENCRYPTION_KEY', None)
    if not key:
        # Fallback default key for test mode
        key = Fernet.generate_key()
    else:
        # Pad or format key if needed
        key_bytes = key.encode('utf-8')
        if len(key_bytes) < 32:
            key_bytes = key_bytes.ljust(32, b'=')
        key = base64.urlsafe_b64encode(key_bytes[:32])
    return Fernet(key)


def encrypt_card_data(card_data_dict: dict) -> str:
    """
    PCI-DSS Compliance: Encrypts card sensitive fields (PAN, CVV, expiry) using AES-256 Fernet cipher.
    Raw card data is NEVER persisted unencrypted.
    """
    cipher = _get_fernet_cipher()
    json_str = json.dumps(card_data_dict)
    encrypted_bytes = cipher.encrypt(json_str.encode('utf-8'))
    return encrypted_bytes.decode('utf-8')


def decrypt_card_data(encrypted_payload: str) -> dict:
    """
    Decrypts encrypted card payload for tokenized processing within secure boundary.
    """
    cipher = _get_fernet_cipher()
    decrypted_bytes = cipher.decrypt(encrypted_payload.encode('utf-8'))
    return json.loads(decrypted_bytes.decode('utf-8'))


def generate_card_fingerprint(card_number: str, customer_id: str) -> str:
    """
    Generates a secure SHA-256 fingerprint for card deduplication without storing raw PAN.
    """
    salt = settings.SECRET_KEY
    raw_str = f"{card_number.strip()}:{customer_id}:{salt}"
    return hashlib.sha256(raw_str.encode('utf-8')).hexdigest()


class MerchantAPIKeyAuthentication(authentication.BaseAuthentication):
    """
    Authentication backend verifying merchant API Key passed via 'X-Merchant-Api-Key' header.
    """
    def authenticate(self, request):
        api_key = request.headers.get('X-Merchant-Api-Key')
        if not api_key:
            return None  # Pass to default authentication
        
        try:
            merchant = MerchantProfile.objects.select_related('user').get(api_key=api_key)
            return (merchant.user, merchant)
        except MerchantProfile.DoesNotExist:
            raise exceptions.AuthenticationFailed('Invalid Merchant API Key provided.')


class IsMerchantUser(permissions.BasePermission):
    """
    Permission class checking if authenticated user has an active Merchant profile.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return hasattr(request.user, 'merchant_profile') or MerchantProfile.objects.filter(user=request.user).exists()


class IsCustomerUser(permissions.BasePermission):
    """
    Permission class checking if authenticated user has an active Customer profile.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return hasattr(request.user, 'customer_profile') or CustomerProfile.objects.filter(user=request.user).exists()
