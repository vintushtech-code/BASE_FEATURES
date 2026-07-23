"""
Authentication & User Management Forms
=======================================

Implements user signup, flexible username/email login, and password reset forms
with custom widget styling matching the central theme_config color scheme.

Security Note:
All form field cleaning uses Django's standard sanitization and validation,
enforcing minimum password lengths and character rules.
"""

from django import forms
from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.forms import (
    UserCreationForm,
    PasswordResetForm,
    SetPasswordForm
)
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class CustomUserCreationForm(UserCreationForm):
    """
    User Registration (Signup) Form.
    Enforces unique email address, valid username format, and strong password policies.
    """
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'placeholder': 'name@example.com',
            'class': 'form-input',
            'autocomplete': 'email',
        }),
        help_text=_("Required. Enter a valid email address.")
    )

    username = forms.CharField(
        required=True,
        max_length=150,
        widget=forms.TextInput(attrs={
            'placeholder': 'Choose a username',
            'class': 'form-input',
            'autocomplete': 'username',
        })
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Apply theme-compatible CSS classes to password fields
        if 'password1' in self.fields:
            self.fields['password1'].widget.attrs.update({
                'class': 'form-input',
                'placeholder': 'Create a strong password',
            })
        if 'password2' in self.fields:
            self.fields['password2'].widget.attrs.update({
                'class': 'form-input',
                'placeholder': 'Confirm password',
            })

    def clean_email(self):
        """
        Verifies that email is unique across all users.
        Uses ORM parameterization to prevent SQL injection.
        """
        email = self.cleaned_data.get('email', '').strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError(_("A user with this email address already exists."))
        return email


class EmailOrUsernameLoginForm(forms.Form):
    """
    User Login Form supporting Username OR Email identification with Password.
    """
    login_identity = forms.CharField(
        label=_("Username or Email"),
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter your username or email',
            'class': 'form-input',
            'autocomplete': 'username',
            'autofocus': True,
        })
    )
    password = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Enter your password',
            'class': 'form-input',
            'autocomplete': 'current-password',
        })
    )
    remember_me = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-checkbox',
        }),
        label=_("Keep me signed in")
    )

    def clean(self):
        cleaned_data = super().clean()
        identity = cleaned_data.get('login_identity')
        password = cleaned_data.get('password')

        if identity and password:
            identity = identity.strip()
            # 1. Try finding user by email first using ORM parameterized lookup
            user_obj = User.objects.filter(email__iexact=identity).first()
            username_to_auth = user_obj.username if user_obj else identity

            # 2. Authenticate credentials
            self.user_cache = authenticate(username=username_to_auth, password=password)

            if self.user_cache is None:
                raise ValidationError(
                    _("Invalid login credentials. Please check your username/email and password."),
                    code='invalid_login'
                )
            elif not self.user_cache.is_active:
                raise ValidationError(
                    _("This account is currently inactive."),
                    code='inactive'
                )

        return cleaned_data

    def get_user(self):
        return getattr(self, 'user_cache', None)


class CustomPasswordResetForm(PasswordResetForm):
    """
    Password Reset Email Request Form.
    """
    email = forms.EmailField(
        max_length=254,
        widget=forms.EmailInput(attrs={
            'placeholder': 'Enter your account email address',
            'class': 'form-input',
            'autocomplete': 'email',
        })
    )


class CustomSetPasswordForm(SetPasswordForm):
    """
    Password Reset Confirmation / New Password Form.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ['new_password1', 'new_password2']:
            if field_name in self.fields:
                self.fields[field_name].widget.attrs.update({
                    'class': 'form-input',
                    'placeholder': 'Enter new password',
                })
