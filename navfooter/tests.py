"""
NavFooter App Unit Tests
========================

Verifies inclusion template tags rendering and context handling for navfooter.
"""

from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.template import Context, Template

User = get_user_model()


class NavfooterTemplateTagsTestCase(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="navuser",
            email="navuser@example.com",
            password="TestPassword123!"
        )

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
