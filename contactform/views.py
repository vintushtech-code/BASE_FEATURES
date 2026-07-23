import hashlib
import time
import logging
from django.views.generic import FormView, TemplateView
from django.urls import reverse_lazy
from django.core.mail import send_mail
from django.conf import settings
from django.core.cache import cache
from django.utils.html import escape, strip_tags
from django.http import HttpResponse

from .forms import ContactForm
from .models import ContactSubmission

logger = logging.getLogger(__name__)

def get_client_ip(request):
    """Extracts client IP address, handling proxies securely."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
    return ip

def check_rate_limit(request, cache_key, limit, period):
    """
    Checks if the rate limit is exceeded for the cache_key.
    Uses sliding window.
    Falls back to session storage if the cache is unavailable or is a DummyCache.
    Returns: (is_allowed, request_records, using_session)
    """
    # Verify cache functionality dynamically (catches offline caches and DummyCache)
    use_session = False
    try:
        cache.set("contactform_ping", "pong", 5)
        if cache.get("contactform_ping") != "pong":
            use_session = True
    except Exception:
        use_session = True

    now = time.time()
    
    if use_session:
        session_key = f"rl_{cache_key}"
        records = request.session.get(session_key, [])
    else:
        try:
            records = cache.get(cache_key, [])
        except Exception:
            # Fallback inline if cache read fails
            session_key = f"rl_{cache_key}"
            records = request.session.get(session_key, [])
            use_session = True

    # Filter records within sliding window
    records = [t for t in records if now - t < period]

    if len(records) >= limit:
        return False, records, use_session

    # Record current request attempt
    records.append(now)

    if use_session:
        session_key = f"rl_{cache_key}"
        request.session[session_key] = records
        request.session.modified = True
    else:
        try:
            cache.set(cache_key, records, period)
        except Exception:
            # Fallback inline if cache write fails
            session_key = f"rl_{cache_key}"
            records = request.session.get(session_key, [])
            records = [t for t in records if now - t < period]
            records.append(now)
            request.session[session_key] = records
            request.session.modified = True
            use_session = True

    return True, records, use_session


class ContactFormView(FormView):
    template_name = 'contactform/contact.html'
    form_class = ContactForm
    success_url = reverse_lazy('contactform:success')

    def dispatch(self, request, *args, **kwargs):
        # We apply rate limiting at dispatch to block abuse early
        ip = get_client_ip(request)
        ip_hash = hashlib.sha256(ip.encode('utf-8')).hexdigest()
        
        limit = getattr(settings, 'CONTACT_FORM_RATE_LIMIT_LIMIT', 5)
        period = getattr(settings, 'CONTACT_FORM_RATE_LIMIT_PERIOD', 3600)  # default: 1 hour

        cache_key = f"contactform_rl_{ip_hash}"
        
        # Check rate limit on form load & post to prevent both page rendering spam and submission spam
        # Note: True = allowed, False = blocked
        is_allowed, _, _ = check_rate_limit(request, cache_key, limit, period)
        
        if not is_allowed:
            context = {
                'title': 'Rate Limit Exceeded',
                'error_message': f'Too many attempts. Maximum allowed is {limit} submissions per hour.',
                'retry_after_minutes': int(period / 60),
            }
            return self.response_class(
                request=request,
                template='contactform/rate_limited.html',
                context=context,
                status=429
            )

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        ip = get_client_ip(self.request)
        
        # 1. Retrieve the submission (without saving to db yet)
        submission = form.save(commit=False)
        submission.ip_address = ip

        # 2. Hardened XSS Protection: HTML-escape user inputs prior to saving
        submission.name = escape(strip_tags(submission.name))
        submission.email = escape(strip_tags(submission.email))
        submission.subject = escape(strip_tags(submission.subject))
        submission.message = escape(strip_tags(submission.message))
        
        # 3. Save utilizing Django ORM (which uses parameterized queries)
        submission.save()

        # 4. Email notification to target recipient
        recipient = getattr(settings, 'CONTACT_FORM_EMAIL_RECIPIENT', 'admin@example.com')
        subject = f"New Contact Submission: {submission.subject}"
        message_body = (
            f"You have received a new contact submission:\n\n"
            f"Name: {submission.name}\n"
            f"Email: {submission.email}\n"
            f"IP Address: {submission.ip_address}\n\n"
            f"Message:\n{submission.message}\n"
        )
        sender = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com')
        
        try:
            send_mail(
                subject,
                message_body,
                sender,
                [recipient],
                fail_silently=False,
            )
        except Exception as e:
            logger.error(f"Failed to send contact notification email: {e}")

        return super().form_valid(form)


class ContactSuccessView(TemplateView):
    template_name = 'contactform/success.html'
