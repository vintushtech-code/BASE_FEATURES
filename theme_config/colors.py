"""
Central Color Palette Configuration Module
==========================================

This file centralizes all theme colors for the entire application.
Changing a single variable or palette value here updates the UI globally
across all apps (login, dashboard, navigation, buttons, cards, inputs).

The colors are exposed via context processor to CSS custom properties (--color-*).
"""

# Core Two-Primary Color System & Palette Specifications

COLOR_PRIMARY = "#111111"       # Primary text & CTA buttons (Sleek Black)
COLOR_SECONDARY = "#FFFFFF"     # Containers, Cards, Cards background (Clean White)
COLOR_BG = "#FFF0F5"            # Page Body Background (Baby Light Pink)
COLOR_TEXT_SUB = "#4A4A4A"      # Subtext, labels, placeholder & secondary text (Soft Greyish Black)

# Additional UI State & Border Utility Tokens derived for clean consistency
COLOR_BORDER = "#E5D6DB"        # Subtle card border matching soft pink background
COLOR_PRIMARY_HOVER = "#2D2D2D"  # CTA Button hover state
COLOR_INPUT_BG = "#FAFAFA"      # Form input fields background
COLOR_SUCCESS = "#155724"       # Success notification text
COLOR_SUCCESS_BG = "#D4EDDA"    # Success alert pill background
COLOR_ERROR = "#721C24"         # Error alert text
COLOR_ERROR_BG = "#F8D7DA"      # Error alert pill background

THEME_PALETTE = {
    "COLOR_PRIMARY": COLOR_PRIMARY,
    "COLOR_SECONDARY": COLOR_SECONDARY,
    "COLOR_BG": COLOR_BG,
    "COLOR_TEXT_SUB": COLOR_TEXT_SUB,
    "COLOR_BORDER": COLOR_BORDER,
    "COLOR_PRIMARY_HOVER": COLOR_PRIMARY_HOVER,
    "COLOR_INPUT_BG": COLOR_INPUT_BG,
    "COLOR_SUCCESS": COLOR_SUCCESS,
    "COLOR_SUCCESS_BG": COLOR_SUCCESS_BG,
    "COLOR_ERROR": COLOR_ERROR,
    "COLOR_ERROR_BG": COLOR_ERROR_BG,
}


def get_css_variables():
    """
    Generates CSS custom property declarations (:root block)
    from THEME_PALETTE dictionary for effortless template injection.
    """
    css_vars = [
        f"--color-primary: {COLOR_PRIMARY};",
        f"--color-secondary: {COLOR_SECONDARY};",
        f"--color-bg: {COLOR_BG};",
        f"--color-subtext: {COLOR_TEXT_SUB};",
        f"--color-border: {COLOR_BORDER};",
        f"--color-primary-hover: {COLOR_PRIMARY_HOVER};",
        f"--color-input-bg: {COLOR_INPUT_BG};",
        f"--color-success: {COLOR_SUCCESS};",
        f"--color-success-bg: {COLOR_SUCCESS_BG};",
        f"--color-error: {COLOR_ERROR};",
        f"--color-error-bg: {COLOR_ERROR_BG};",
    ]
    return "\n  ".join(css_vars)
