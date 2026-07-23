"""
Central Color Palette Configuration Module
==========================================

This file centralizes all theme colors for the entire application.
Changing a single variable or palette value here updates the UI globally
across all apps (login, dashboard, navigation, buttons, cards, inputs).

The colors are exposed via context processor to CSS custom properties (--color-*).
Supports both Light Theme (default) and Dark Theme (activated via data-theme="dark" on <html>).
"""

# ============================================================
# LIGHT THEME PALETTE (Default)
# ============================================================

COLOR_PRIMARY = "#111111"        # Primary text & CTA buttons (Sleek Black)
COLOR_SECONDARY = "#FFFFFF"      # Containers, Cards background (Clean White)
COLOR_BG = "#FFF0F5"             # Page Body Background (Baby Light Pink)
COLOR_TEXT_SUB = "#4A4A4A"       # Subtext, labels, placeholder & secondary text
COLOR_BORDER = "#E5D6DB"         # Subtle card border matching soft pink background
COLOR_PRIMARY_HOVER = "#2D2D2D" # CTA Button hover state
COLOR_INPUT_BG = "#FAFAFA"       # Form input fields background
COLOR_SUCCESS = "#155724"        # Success notification text
COLOR_SUCCESS_BG = "#D4EDDA"     # Success alert pill background
COLOR_ERROR = "#721C24"          # Error alert text
COLOR_ERROR_BG = "#F8D7DA"       # Error alert pill background

# ============================================================
# DARK THEME PALETTE
# ============================================================

DARK_COLOR_PRIMARY = "#F1F1F1"       # Primary text & CTA (Near White)
DARK_COLOR_SECONDARY = "#1E1E2E"     # Card & Surface background (Deep Dark Indigo)
DARK_COLOR_BG = "#12121C"            # Page Background (Very Dark Indigo-Black)
DARK_COLOR_TEXT_SUB = "#A0A0B8"      # Subtext (Soft Muted Lavender-Grey)
DARK_COLOR_BORDER = "#2E2E45"        # Subtle border in dark context
DARK_COLOR_PRIMARY_HOVER = "#DCDCF0" # CTA hover (Softer White)
DARK_COLOR_INPUT_BG = "#252537"      # Input fields background (Dark Container)
DARK_COLOR_SUCCESS = "#75D69C"       # Success text (Muted Green)
DARK_COLOR_SUCCESS_BG = "#1A3A2A"    # Success pill bg (Deep Dark Green)
DARK_COLOR_ERROR = "#F28B82"         # Error text (Soft Red)
DARK_COLOR_ERROR_BG = "#3A1A1A"      # Error pill bg (Deep Dark Red)


THEME_PALETTE = {
    # Light
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
    # Dark
    "DARK_COLOR_PRIMARY": DARK_COLOR_PRIMARY,
    "DARK_COLOR_SECONDARY": DARK_COLOR_SECONDARY,
    "DARK_COLOR_BG": DARK_COLOR_BG,
    "DARK_COLOR_TEXT_SUB": DARK_COLOR_TEXT_SUB,
    "DARK_COLOR_BORDER": DARK_COLOR_BORDER,
    "DARK_COLOR_PRIMARY_HOVER": DARK_COLOR_PRIMARY_HOVER,
    "DARK_COLOR_INPUT_BG": DARK_COLOR_INPUT_BG,
    "DARK_COLOR_SUCCESS": DARK_COLOR_SUCCESS,
    "DARK_COLOR_SUCCESS_BG": DARK_COLOR_SUCCESS_BG,
    "DARK_COLOR_ERROR": DARK_COLOR_ERROR,
    "DARK_COLOR_ERROR_BG": DARK_COLOR_ERROR_BG,
}


def get_css_variables():
    """
    Generates CSS custom property declarations for both light and dark themes.
    Enables single-source-of-truth style management in python while allowing
    correct cascading and overriding.
    """
    light_vars = [
        f"--color-primary: {COLOR_PRIMARY};",
        f"--color-secondary: {COLOR_SECONDARY};",
        f"--color-bg: {COLOR_BG};",
        f"--color-subtext: {COLOR_TEXT_SUB};",
        f"--color-border: {COLOR_BORDER};",
        f"--color-primary-hover: {COLOR_PRIMARY_HOVER};",
        f"--color-input-bg: {COLOR_INPUT_BG};",
        f"--color-success: {COLOR_SUCCESS};",
        f"--color-success-bg: {COLOR_SUCCESS_BG};",
        f"--color-success-border: rgba(21, 87, 36, 0.25);",
        f"--color-error: {COLOR_ERROR};",
        f"--color-error-bg: {COLOR_ERROR_BG};",
        f"--color-error-border: rgba(114, 28, 36, 0.25);",
        f"--color-info: #274e13;",
        f"--color-info-bg: #e2f0d9;",
        f"--color-info-border: rgba(39, 78, 19, 0.2);",
        f"--color-focus-ring: rgba(17, 17, 17, 0.1);",
        f"--color-avatar-shadow: rgba(0, 0, 0, 0.12);",
    ]

    dark_vars = [
        f"--color-primary: {DARK_COLOR_PRIMARY};",
        f"--color-secondary: {DARK_COLOR_SECONDARY};",
        f"--color-bg: {DARK_COLOR_BG};",
        f"--color-subtext: {DARK_COLOR_TEXT_SUB};",
        f"--color-border: {DARK_COLOR_BORDER};",
        f"--color-primary-hover: {DARK_COLOR_PRIMARY_HOVER};",
        f"--color-input-bg: {DARK_COLOR_INPUT_BG};",
        f"--color-success: {DARK_COLOR_SUCCESS};",
        f"--color-success-bg: {DARK_COLOR_SUCCESS_BG};",
        f"--color-success-border: rgba(117, 214, 156, 0.25);",
        f"--color-error: {DARK_COLOR_ERROR};",
        f"--color-error-bg: {DARK_COLOR_ERROR_BG};",
        f"--color-error-border: rgba(242, 139, 130, 0.25);",
        f"--color-info: {DARK_COLOR_SUCCESS};",
        f"--color-info-bg: {DARK_COLOR_SUCCESS_BG};",
        f"--color-info-border: rgba(117, 214, 156, 0.25);",
        f"--color-focus-ring: rgba(241, 241, 241, 0.12);",
        f"--color-avatar-shadow: rgba(0, 0, 0, 0.4);",
    ]

    light_str = "\n  ".join(light_vars)
    dark_str = "\n  ".join(dark_vars)

    return f":root {{\n  {light_str}\n}}\n\n[data-theme='dark'] {{\n  {dark_str}\n}}"

