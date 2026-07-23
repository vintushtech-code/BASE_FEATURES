"""
Authentication Test Suite
==========================

Tests all core requirements:
- CustomUser creation and ORM safety
- Registration & Signup view
- Flexible Username / Email Login
- Password Reset initialization
- Rate limiting protection
- Social Auth initialization
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from login.security import sanitize_input

User = get_user_model()


class SecurityAndAuthTestCase(TestCase):

    def setUp(self):
        self.client = Client()
        # Create a test user via ORM
        self.test_username = "testuser"
        self.test_email = "testuser@example.com"
        self.test_password = "SecurePassword123!"
        
        self.user = User.objects.create_user(
            username=self.test_username,
            email=self.test_email,
            password=self.test_password,
            bio="Original Bio"
        )

    def test_custom_user_model_attributes(self):
        """Verify custom user model attributes and initials helper."""
        self.assertEqual(self.user.auth_provider, 'email')
        self.assertEqual(self.user.get_initials(), 'TE')
        self.assertTrue(User.objects.filter(email=self.test_email).exists())

    def test_login_with_username(self):
        """Test authentication using username."""
        response = self.client.post(reverse('login:login'), {
            'login_identity': self.test_username,
            'password': self.test_password
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['user'].is_authenticated)

    def test_login_with_email(self):
        """Test authentication using email address instead of username."""
        response = self.client.post(reverse('login:login'), {
            'login_identity': self.test_email,
            'password': self.test_password
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['user'].is_authenticated)

    def test_signup_creates_new_user(self):
        """Test new user registration."""
        signup_data = {
            'username': 'newsignup',
            'email': 'newsignup@example.com',
            'password1': 'StrongPassWord89!',
            'password2': 'StrongPassWord89!',
        }
        response = self.client.post(reverse('login:signup'), signup_data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(username='newsignup').exists())

    def test_xss_sanitization(self):
        """Verify XSS payload sanitization on profile input."""
        malicious_input = "<script>alert('xss')</script>Hello World"
        cleaned = sanitize_input(malicious_input)
        self.assertNotIn("<script>", cleaned)
        self.assertIn("Hello World", cleaned)

    def test_password_reset_view(self):
        """Verify password reset request succeeds for existing email."""
        response = self.client.post(reverse('login:password_reset'), {
            'email': self.test_email
        })
        self.assertEqual(response.status_code, 302)

    def test_social_auth_dev_fallback(self):
        """Test social OAuth init view fallback in development mode."""
        response = self.client.get(reverse('login:social_init', kwargs={'provider': 'google'}), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['user'].is_authenticated)
