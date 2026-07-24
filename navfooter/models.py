from django.db import models
from django.core.exceptions import ValidationError

class SocialMediaLink(models.Model):
    """
    Model representing social media presence links that can be shown/hidden
    in the site footer via the Django Admin panel.
    """
    PLATFORM_CHOICES = [
        ('whatsapp', 'WhatsApp'),
        ('linkedin', 'LinkedIn'),
        ('facebook', 'Facebook'),
        ('instagram', 'Instagram'),
        ('github', 'GitHub'),
    ]

    platform = models.CharField(
        max_length=20, 
        choices=PLATFORM_CHOICES, 
        unique=True, 
        verbose_name="Platform Name"
    )
    url = models.URLField(
        max_length=500, 
        blank=True, 
        default="", 
        verbose_name="Profile/Chat Link", 
        help_text="Enter the full URL (e.g., https://wa.me/yourphone or https://linkedin.com/in/username)"
    )
    is_active = models.BooleanField(
        default=False, 
        verbose_name="Show in Footer", 
        help_text="Toggle to show/hide this social media link in the footer"
    )

    class Meta:
        verbose_name = "Social Media Link"
        verbose_name_plural = "Social Media Links"
        ordering = ['platform']

    def clean(self):
        super().clean()
        if self.is_active and not self.url:
            raise ValidationError({
                'url': "You cannot activate a social media link without providing its URL."
            })

    def __str__(self):
        return f"{self.get_platform_display()} ({'Active' if self.is_active else 'Inactive'})"


class NavbarSettings(models.Model):
    """
    Singleton model for central Navbar settings and configuration.
    """
    logo_image_url = models.URLField(
        max_length=500, 
        blank=True, 
        default="", 
        verbose_name="Logo External URL", 
        help_text="Provide an external image URL to use as the navbar logo (e.g. https://example.com/logo.png)."
    )
    logo_image_file = models.ImageField(
        upload_to='navbar_logos/', 
        blank=True, 
        null=True, 
        verbose_name="Logo Local File", 
        help_text="Upload a local image file to use as the navbar logo. If both file and URL are specified, the uploaded file takes precedence."
    )

    class Meta:
        verbose_name = "Navbar Settings"
        verbose_name_plural = "Navbar Settings"

    def __str__(self):
        return "Navbar Configuration Settings"

