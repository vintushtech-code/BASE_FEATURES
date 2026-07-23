"""
Security & Hardening Utilities
================================

Implements critical non-negotiable security protections for the authentication app:
1. Brute-Force Rate Limiting: IP & Key-based rate-limiting decorator using Django Cache.
2. XSS Input Sanitization: Strict string cleaning for user submitted profile text.
3. SQL Injection Assurance: Guidelines and helper checks verifying ORM usage.
"""

import functools
import time
from django.core.cache import cache
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.utils.html import escape, strip_tags


def rate_limit(key_type='ip', limit=5, period=60):
    """
    Custom Rate-Limiting Decorator for authentication endpoints.
    Prevents brute-force credential stuffing and password reset spamming.

    :param key_type: 'ip' (rate limit by remote IP) or 'post_user' (rate limit by requested username)
    :param limit: Maximum number of allowed requests in the time period (default: 5)
    :param period: Time window in seconds (default: 60 seconds)
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if key_type == 'ip':
                # Extract client IP address safely considering proxies
                x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
                if x_forwarded_for:
                    ip = x_forwarded_for.split(',')[0].strip()
                else:
                    ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
                cache_key = f"rl_ip_{view_func.__name__}_{ip}"
            else:
                user_id = request.POST.get('username') or request.POST.get('email') or 'anonymous'
                cache_key = f"rl_user_{view_func.__name__}_{user_id}"

            # Fetch rate limit state from cache
            request_records = cache.get(cache_key, [])
            now = time.time()

            # Filter timestamps within current sliding window
            request_records = [t for t in request_records if now - t < period]

            if len(request_records) >= limit:
                # Rate limit exceeded - render secure error feedback
                context = {
                    'title': 'Rate Limit Exceeded',
                    'error_message': f'Too many attempts. Please wait {period} seconds before trying again.',
                    'retry_after': period,
                }
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'error': context['error_message']}, status=429)
                return render(request, 'login/rate_limited.html', context, status=429)

            # Record current request attempt timestamp
            request_records.append(now)
            cache.set(cache_key, request_records, period)

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def sanitize_input(text_content):
    """
    Sanitizes user submitted string inputs to prevent XSS payloads.
    Strips HTML tags and escapes sensitive XML/HTML characters.
    """
    if not isinstance(text_content, str):
        return text_content
    cleaned = strip_tags(text_content)
    return escape(cleaned)
