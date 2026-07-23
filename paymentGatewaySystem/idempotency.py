import hashlib
import json
import logging
from datetime import timedelta
from functools import wraps
from django.utils import timezone
from rest_framework.response import Response
from rest_framework import status
from paymentGatewaySystem.models import IdempotencyRecord

logger = logging.getLogger(__name__)


def compute_request_hash(path: str, data: dict or str) -> str:
    """
    Computes SHA-256 hash of request endpoint path and request body data.
    """
    if isinstance(data, dict):
        # Sort keys for deterministic JSON string hashing
        raw_body = json.dumps(data, sort_keys=True)
    else:
        raw_body = str(data or "")
    
    combined = f"{path}:{raw_body}"
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()


def handle_idempotency(request, view_func, *args, **kwargs):
    """
    Core Idempotency Engine.
    Intercepts client request with Idempotency-Key header.
    Returns cached response if duplicate key detected, preventing duplicate charges.
    """
    idempotency_key = request.headers.get('Idempotency-Key') or request.META.get('HTTP_IDEMPOTENCY_KEY')

    # If no idempotency key provided, proceed normally
    if not idempotency_key:
        return view_func(request, *args, **kwargs)

    req_path = request.path
    req_data = request.data if hasattr(request, 'data') else {}
    req_hash = compute_request_hash(req_path, req_data)

    # Check for existing idempotency record
    existing_record = IdempotencyRecord.objects.filter(key=idempotency_key).first()

    if existing_record:
        if existing_record.is_expired():
            # Clean up expired record
            existing_record.delete()
        else:
            # Check request payload hash match
            if existing_record.request_hash != req_hash:
                logger.warning(f"Idempotency Key Conflict: {idempotency_key} used with different payload")
                return Response(
                    {
                        "error": "DUPLICATE_REQUEST_REJECTED",
                        "message": "Idempotency-Key already used with a different request payload.",
                    },
                    status=status.HTTP_409_CONFLICT
                )

            logger.info(f"Returning cached response for Idempotency-Key: {idempotency_key}")
            cached_data = existing_record.response_body
            cached_data["_cached_idempotent_response"] = True
            return Response(cached_data, status=existing_record.response_status)

    # Execute original view logic
    response = view_func(request, *args, **kwargs)

    # Cache successful or client response (only status code < 500)
    if response.status_code < 500:
        expires_at = timezone.now() + timedelta(hours=24)
        try:
            resp_body = response.data if hasattr(response, 'data') else {}
            IdempotencyRecord.objects.create(
                key=idempotency_key,
                request_path=req_path,
                request_hash=req_hash,
                response_status=response.status_code,
                response_body=resp_body,
                expires_at=expires_at
            )
        except Exception as e:
            logger.error(f"Failed to record idempotency cache for key {idempotency_key}: {e}")

    return response


def idempotent_api():
    """
    Decorator for DRF API view functions to enforce HTTP Idempotency-Key support.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            return handle_idempotency(request, func, *args, **kwargs)
        return wrapper
    return decorator
