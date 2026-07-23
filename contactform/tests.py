import time
from django.test import TestCase, Client
from django.urls import reverse
from django.core import mail
from django.core.signing import Signer
from django.core.cache import cache
from django.conf import settings
from contactform.models import ContactSubmission
from contactform.forms import ContactForm

class ContactSubmissionModelTest(TestCase):
    def test_model_creation(self):
        sub = ContactSubmission.objects.create(
            name="John Doe",
            email="john@example.com",
            subject="Hello",
            message="Test message",
            ip_address="127.0.0.1"
        )
        self.assertEqual(ContactSubmission.objects.count(), 1)
        expected_str = f"Submission from John Doe - Hello ({sub.created_at.strftime('%Y-%m-%d %H:%M')})"
        self.assertEqual(str(sub), expected_str)

class ContactFormTest(TestCase):
    def test_valid_form_submission(self):
        signer = Signer()
        # Bypassing the minimum time-lock check by simulating the form was loaded 5 seconds ago
        past_time = str(int(time.time()) - 5)
        signed_ts = signer.sign(past_time)
        
        form_data = {
            'name': 'Alice Smith',
            'email': 'alice@example.com',
            'subject': 'Inquiry',
            'message': 'Hi there!',
            'website': '',  # Honeypot must be empty
            'submission_security': signed_ts
        }
        form = ContactForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_honeypot_triggers_spam(self):
        signer = Signer()
        past_time = str(int(time.time()) - 5)
        signed_ts = signer.sign(past_time)
        
        form_data = {
            'name': 'Alice Smith',
            'email': 'alice@example.com',
            'subject': 'Inquiry',
            'message': 'Hi there!',
            'website': 'spam-bot-value',  # Honeypot filled!
            'submission_security': signed_ts
        }
        form = ContactForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('website', form.errors)

    def test_timelock_triggers_spam_for_instant_submission(self):
        signer = Signer()
        # Form submitted instantly (0 seconds elapsed)
        current_time = str(int(time.time()))
        signed_ts = signer.sign(current_time)
        
        form_data = {
            'name': 'Alice Smith',
            'email': 'alice@example.com',
            'subject': 'Inquiry',
            'message': 'Hi there!',
            'website': '',
            'submission_security': signed_ts
        }
        form = ContactForm(data=form_data)
        self.assertFalse(form.is_valid())
        # The ValidationError is raised in clean() so it's a non-field error
        self.assertIn('__all__', form.errors)
        self.assertEqual(form.errors['__all__'][0], "Form submitted too quickly. Please try again.")

class ContactFormViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('contactform:contact')
        cache.clear()

    def test_view_renders_correctly(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'contactform/contact.html')
        self.assertIn('form', response.context)

    def test_rate_limiting_triggered(self):
        # Trigger the rate limit by posting multiple times (exceeding limit of 5 per hour)
        signer = Signer()
        
        # We need to simulate past time-lock on each submission to pass form validation
        for i in range(6):
            past_time = str(int(time.time()) - 5)
            signed_ts = signer.sign(past_time)
            form_data = {
                'name': f'Tester {i}',
                'email': f'tester{i}@example.com',
                'subject': 'Test Subject',
                'message': 'Test message content',
                'website': '',
                'submission_security': signed_ts
            }
            response = self.client.post(self.url, form_data)
            
            if i < 5:
                self.assertEqual(response.status_code, 302)  # Successful redirect to success page
            else:
                self.assertEqual(response.status_code, 429)  # 6th attempt is rate limited (429 Too Many Requests)
                self.assertTemplateUsed(response, 'contactform/rate_limited.html')
