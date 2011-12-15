from django.conf import settings

from social_auth.models import User
from social_auth.signals import socialauth_not_registered

from social_auth.backends.pipeline import warn_setting

def create_user(backend, details, response, uid, username, user=None, *args,
                **kwargs):
    """Create user without email. Depends on get_username pipeline."""
    if user:
        return {'user': user}
    if not username:
        return None

    warn_setting('SOCIAL_AUTH_CREATE_USERS', 'create_user')

    if not getattr(settings, 'SOCIAL_AUTH_CREATE_USERS', True):
        # Send signal for cases where tracking failed registering is useful.
        socialauth_not_registered.send(sender=backend.__class__,
                                       uid=uid,
                                       response=response,
                                       details=details)
        return None

    return {
        'user': User.objects.create_user(username=username, email=""),
        'is_new': True
    }

