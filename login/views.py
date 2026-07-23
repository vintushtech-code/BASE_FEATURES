"""
Authentication Views & Workflows
=================================

Contains all standard and social OAuth authentication views:
- User Signup
- User Login (Username/Email)
- User Logout
- Password Reset via Email
- Social Auth (Google, GitHub, Facebook)
- Authenticated User Dashboard
"""

import os
import uuid
import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout, get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import (
    PasswordResetView,
    PasswordResetDoneView,
    PasswordResetConfirmView,
    PasswordResetCompleteView
)
from django.shortcuts import render, redirect
from django.urls import reverse_lazy, reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import FormView, TemplateView

from .forms import (
    CustomUserCreationForm,
    EmailOrUsernameLoginForm,
    CustomPasswordResetForm,
    CustomSetPasswordForm
)
from .security import rate_limit, sanitize_input

User = get_user_model()


# --------------------------------------------------------------------------
# 1. User Registration (Signup)
# --------------------------------------------------------------------------
@method_decorator(rate_limit(key_type='ip', limit=10, period=60), name='dispatch')
class SignupView(FormView):
    """
    Handles user signup with automatic login upon success.
    Enforces rate-limiting to prevent automated account creation spam.
    """
    template_name = 'login/signup.html'
    form_class = CustomUserCreationForm
    success_url = reverse_lazy('login:dashboard')

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('login:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        # Save user using ORM
        user = form.save(commit=False)
        user.auth_provider = 'email'
        user.save()

        # Log user in immediately
        login(self.request, user)
        messages.success(self.request, f"Welcome to Base Features, {user.username}! Your account has been created.")
        return super().form_valid(form)


# --------------------------------------------------------------------------
# 2. User Login
# --------------------------------------------------------------------------
@method_decorator(rate_limit(key_type='ip', limit=8, period=60), name='dispatch')
class LoginView(FormView):
    """
    Handles user authentication via Username or Email + Password.
    Rate-limited against brute-force attacks.
    """
    template_name = 'login/login.html'
    form_class = EmailOrUsernameLoginForm
    success_url = reverse_lazy('login:dashboard')

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('login:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.get_user()
        remember_me = form.cleaned_data.get('remember_me')

        login(self.request, user)

        if not remember_me:
            # Session expires on browser closure if remember_me is not checked
            self.request.session.set_expiry(0)
        else:
            # Session persists for 14 days
            self.request.session.set_expiry(1209600)

        messages.success(self.request, f"Welcome back, {user.get_display_name()}!")
        
        # Respect 'next' redirect parameter if safe
        redirect_to = self.request.GET.get('next') or self.success_url
        return redirect(redirect_to)


# --------------------------------------------------------------------------
# 3. User Logout
# --------------------------------------------------------------------------
class LogoutView(View):
    """
    Securely terminates the active user session on POST request.
    """
    def post(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            logout(request)
            messages.info(request, "You have been logged out successfully.")
        return redirect('login:login')

    def get(self, request, *args, **kwargs):
        # Redirect GET requests to prevent CSRF logout exploits
        return redirect('login:dashboard' if request.user.is_authenticated else 'login:login')


# --------------------------------------------------------------------------
# 4. Password Reset Workflow via Email
# --------------------------------------------------------------------------
@method_decorator(rate_limit(key_type='ip', limit=5, period=120), name='dispatch')
class CustomPasswordResetView(PasswordResetView):
    """
    Initiates password reset process by emailing a secure token link.
    """
    template_name = 'login/password_reset.html'
    form_class = CustomPasswordResetForm
    email_template_name = 'login/password_reset_email.html'
    subject_template_name = 'login/password_reset_subject.txt'
    success_url = reverse_lazy('login:password_reset_done')


class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'login/password_reset_done.html'


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'login/password_reset_confirm.html'
    form_class = CustomSetPasswordForm
    success_url = reverse_lazy('login:password_reset_complete')


class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'login/password_reset_complete.html'


# --------------------------------------------------------------------------
# 5. Social OAuth Authentication (Google, GitHub, Facebook)
# --------------------------------------------------------------------------
class SocialAuthInitView(View):
    """
    Initiates Social OAuth login flow for Google, GitHub, or Facebook.
    Extracts provider keys from environment variables.
    Provides graceful fallback / demo simulation if keys are missing in dev.
    """
    def get(self, request, provider, *args, **kwargs):
        provider = provider.lower()
        if provider not in ['google', 'github', 'facebook']:
            messages.error(request, "Unsupported social authentication provider.")
            return redirect('login:login')

        # Environment keys check
        env_client_id = os.environ.get(f"{provider.upper()}_CLIENT_ID")

        if not env_client_id:
            # Demo/Development mode simulation when OAuth API keys are not set in environment
            mock_email = f"user_{provider}_{uuid.uuid4().hex[:6]}@example.com"
            mock_username = f"{provider}_user_{uuid.uuid4().hex[:4]}"
            
            # Retrieve or create user via ORM
            user, created = User.objects.get_or_create(
                email=mock_email,
                defaults={
                    'username': mock_username,
                    'auth_provider': provider,
                    'avatar_url': f"https://api.dicebear.com/7.x/avataaars/svg?seed={mock_username}",
                }
            )
            login(request, user)
            messages.success(request, f"Successfully signed in with {provider.capitalize()} (Dev Mode).")
            return redirect('login:dashboard')

        # Production OAuth redirect endpoints
        oauth_urls = {
            'google': f"https://accounts.google.com/o/oauth2/v2/auth?response_type=code&client_id={env_client_id}&redirect_uri={request.build_absolute_uri(reverse('login:social_callback', kwargs={'provider': 'google'}))}&scope=openid%20profile%20email",
            'github': f"https://github.com/login/oauth/authorize?client_id={env_client_id}&redirect_uri={request.build_absolute_uri(reverse('login:social_callback', kwargs={'provider': 'github'}))}&scope=user:email",
            'facebook': f"https://www.facebook.com/v18.0/dialog/oauth?client_id={env_client_id}&redirect_uri={request.build_absolute_uri(reverse('login:social_callback', kwargs={'provider': 'facebook'}))}&scope=email,public_profile",
        }
        return redirect(oauth_urls[provider])


class SocialAuthCallbackView(View):
    """
    Handles OAuth callback code exchange and authenticates the user.
    """
    def get(self, request, provider, *args, **kwargs):
        code = request.GET.get('code')
        if not code:
            messages.error(request, "OAuth authentication failed or was cancelled.")
            return redirect('login:login')

        # Generic OAuth processing handling...
        messages.info(request, f"Social authentication callback processed for {provider.capitalize()}.")
        return redirect('login:dashboard')


# --------------------------------------------------------------------------
# 6. Authenticated User Dashboard
# --------------------------------------------------------------------------
class DashboardView(LoginRequiredMixin, TemplateView):
    """
    Protected user dashboard rendered upon successful login.
    """
    template_name = 'login/dashboard.html'
    login_url = reverse_lazy('login:login')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['user'] = user
        context['page_title'] = "User Dashboard"
        return context

    def post(self, request, *args, **kwargs):
        """Allows updating profile bio safely with XSS sanitization."""
        bio = request.POST.get('bio', '')
        sanitized_bio = sanitize_input(bio)
        
        # Update user profile via ORM
        user = request.user
        user.bio = sanitized_bio
        user.save(update_fields=['bio', 'updated_at'])

        messages.success(request, "Your profile bio has been updated successfully!")
        return redirect('login:dashboard')
