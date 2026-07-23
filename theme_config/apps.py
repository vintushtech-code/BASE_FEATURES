"""
Theme Config App Definition
Provides centralized color palette configuration and layout templates
for Base Features Django projects.
"""

from django.apps import AppConfig


class ThemeConfigConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'theme_config'
    verbose_name = 'Centralized Theme Configuration'
