"""
NavFooter App Unit Tests
========================

Verifies inclusion template tags rendering and context handling for navfooter, including the new configurable footer social media links.
"""

from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.template import Context, Template
from django.core.exceptions import ValidationError
from navfooter.models import SocialMediaLink, NavbarSettings

User = get_user_model()


class NavfooterTemplateTagsTestCase(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="navuser",
            email="navuser@example.com",
            password="TestPassword123!"
        )
        # Clear any pre-populated data from migrations to have a clean slate in tests
        SocialMediaLink.objects.all().delete()
        NavbarSettings.objects.all().delete()

    def test_navbar_tag_rendering(self):
        """Verify {% render_navbar %} inclusion tag executes cleanly."""
        request = self.factory.get('/')
        request.user = self.user

        out = Template(
            "{% load navfooter_tags %}"
            "{% render_navbar %}"
        ).render(Context({'request': request}))

        self.assertIn("Base Features", out)
        self.assertIn("Dashboard", out)
        self.assertIn("Logout", out)

    def test_footer_tag_rendering(self):
        """Verify {% render_footer %} inclusion tag executes cleanly."""
        out = Template(
            "{% load navfooter_tags %}"
            "{% render_footer %}"
        ).render(Context({}))

        self.assertIn("Base Features", out)
        self.assertIn("Modular &amp; Secure", out)

    def test_footer_renders_active_social_links(self):
        """Verify that footer renders active links and hides inactive ones."""
        # Create active and inactive links
        SocialMediaLink.objects.create(platform='github', url='https://github.com/myclient', is_active=True)
        SocialMediaLink.objects.create(platform='linkedin', url='https://linkedin.com/in/myclient', is_active=False)

        out = Template(
            "{% load navfooter_tags %}"
            "{% render_footer %}"
        ).render(Context({}))

        # Active GitHub link should render
        self.assertIn("https://github.com/myclient", out)
        self.assertIn("footer-social-icon--github", out)

        # Inactive LinkedIn link should NOT render
        self.assertNotIn("https://linkedin.com/in/myclient", out)
        self.assertNotIn("footer-social-icon--linkedin", out)

    def test_social_media_link_validation(self):
        """Verify that validation fails when an active link has an empty URL."""
        link = SocialMediaLink(platform='whatsapp', url='', is_active=True)
        with self.assertRaises(ValidationError):
            link.full_clean()

    def test_navbar_renders_custom_logo(self):
        """Verify that navbar renders custom logo image when configured."""
        NavbarSettings.objects.create(logo_image_url="https://example.com/custom_logo.png")
        request = self.factory.get('/')
        request.user = self.user

        out = Template(
            "{% load navfooter_tags %}"
            "{% render_navbar %}"
        ).render(Context({'request': request}))

        self.assertIn("https://example.com/custom_logo.png", out)
