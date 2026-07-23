"""
Theme Configuration Context Processors
=======================================

Automatically injects central theme palette variables into template context,
ensuring all apps seamlessly inherit the global color scheme.
"""

from .colors import THEME_PALETTE, get_css_variables, COLOR_PRIMARY, COLOR_SECONDARY, COLOR_BG, COLOR_TEXT_SUB


def theme_colors(request):
    """
    Context processor to make color variables accessible in all templates
    as both Python dictionary keys and raw CSS variables block.
    """
    return {
        'THEME': THEME_PALETTE,
        'COLOR_PRIMARY': COLOR_PRIMARY,
        'COLOR_SECONDARY': COLOR_SECONDARY,
        'COLOR_BG': COLOR_BG,
        'COLOR_TEXT_SUB': COLOR_TEXT_SUB,
        'THEME_CSS_VARIABLES': get_css_variables(),
    }
