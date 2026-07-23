"""
Custom Password Reset Token Generator
======================================

Django 3.2+ changed PasswordResetTokenGenerator to include the user's
`last_login` timestamp in the token hash. This causes tokens to be
immediately invalidated if the user logs in after requesting a reset.

This custom generator excludes `last_login` from the hash so that:
1. Tokens remain valid for their full timeout duration regardless of
   user login activity.
2. The first click on a password reset link always works correctly.

Security Note:
- Tokens still expire after PASSWORD_RESET_TIMEOUT seconds (default 72 hours).
- Tokens are still tied to the user's hashed password, so they become
  invalid the moment the password is successfully changed.
- Each token is cryptographically unique to the user and timestamp.
"""

from django.contrib.auth.tokens import PasswordResetTokenGenerator


class PasswordResetTokenGeneratorNoLastLogin(PasswordResetTokenGenerator):
    """
    Custom token generator that removes last_login from the hash value.

    The default Django generator includes last_login which invalidates
    reset tokens whenever the user logs in. This is overly strict for
    password reset flows and causes "link expired" on first click.
    """

    def _make_hash_value(self, user, timestamp):
        """
        Override hash to exclude last_login.
        Token is still bound to:
        - user.pk (user identity)
        - timestamp (expiry window)
        - user.password (invalidated after successful reset)
        - user.is_active (invalidated if account is deactivated)
        """
        login_timestamp = ''  # Deliberately excluded - prevents premature invalidation
        return (
            str(user.pk)
            + str(timestamp)
            + str(user.password)
            + str(user.is_active)
        )


# Singleton instance to use in views
password_reset_token_generator = PasswordResetTokenGeneratorNoLastLogin()
