"""
NavFooter Inclusion Template Tags
=================================

Provides reusable Django template tags:
- {% render_navbar %}: Renders the application header & navigation bar.
- {% render_footer %}: Renders the application footer section.
"""

from django import template

register = template.Library()


@register.inclusion_tag('navfooter/navbar.html', takes_context=True)
def render_navbar(context, brand_name="Base Features", brand_short="BF"):
    """
    Renders the unified, theme-aware navigation bar.
    Inherits user session state and current request context.
    """
    from navfooter.models import NavbarSettings
    request = context.get('request')
    user = getattr(request, 'user', None) if request else context.get('user')
    
    navbar_settings = None
    try:
        navbar_settings = NavbarSettings.objects.first()
    except Exception:
        # Fallback if DB migrations are not yet run
        pass

    return {
        'request': request,
        'user': user,
        'brand_name': brand_name,
        'brand_short': brand_short,
        'navbar_settings': navbar_settings,
    }


@register.inclusion_tag('navfooter/footer.html', takes_context=True)
def render_footer(context, tagline="Modular & Secure Django Components Library"):
    """
    Renders the unified footer section.
    """
    from navfooter.models import SocialMediaLink, NavbarSettings
    social_links = []
    navbar_settings = None
    try:
        social_links = list(SocialMediaLink.objects.filter(is_active=True))
        navbar_settings = NavbarSettings.objects.first()
    except Exception:
        # Fallback to empty list if DB migrations are not yet run
        pass

    return {
        'tagline': tagline,
        'social_links': social_links,
        'navbar_settings': navbar_settings,
    }
