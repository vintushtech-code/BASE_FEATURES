"""
Login App URL Routing Architecture
===================================

Defines clean, self-contained endpoints for all authentication workflows.
Can be mounted into any Django project's root urls.py with minimal setup.
"""

from django.urls import path
from . import views

app_name = 'login'

urlpatterns = [
    # Main Authenticated Landing Page / Dashboard
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),

    # Core Authentication Routes
    path('login/', views.LoginView.as_view(), name='login'),
    path('signup/', views.SignupView.as_view(), name='signup'),
    path('logout/', views.LogoutView.as_view(), name='logout'),

    # Password Reset Flow Routes
    path('password-reset/', views.CustomPasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', views.CustomPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('password-reset/confirm/<uidb64>/<token>/', views.CustomPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password-reset/complete/', views.CustomPasswordResetCompleteView.as_view(), name='password_reset_complete'),

    # Social OAuth Routes
    path('oauth/<str:provider>/', views.SocialAuthInitView.as_view(), name='social_init'),
    path('oauth/callback/<str:provider>/', views.SocialAuthCallbackView.as_view(), name='social_callback'),
]
