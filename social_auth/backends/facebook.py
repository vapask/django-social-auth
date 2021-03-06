"""
Facebook OAuth support.

This contribution adds support for Facebook OAuth service. The settings
FACEBOOK_APP_ID and FACEBOOK_API_SECRET must be defined with the values
given by Facebook application registration process.

Extended permissions are supported by defining FACEBOOK_EXTENDED_PERMISSIONS
setting, it must be a list of values to request.

By default account id and token expiration time are stored in extra_data
field, check OAuthBackend class for details on how to extend it.
"""
import logging
logger = logging.getLogger(__name__)


import cgi
from urllib import urlencode
from urllib2 import urlopen
import base64
import hmac
import hashlib
import time

from django.conf import settings
from django.utils import simplejson
from django.contrib.auth import authenticate

from social_auth.backends import BaseOAuth2, OAuthBackend, USERNAME
from social_auth.utils import sanitize_log_data


# Facebook configuration
EXPIRES_NAME = getattr(settings, 'SOCIAL_AUTH_EXPIRATION', 'expires')
FACEBOOK_ME = 'https://graph.facebook.com/me?'


class FacebookBackend(OAuthBackend):
    """Facebook OAuth2 authentication backend"""
    name = 'facebook'
    # Default extra data to store
    EXTRA_DATA = [('id', 'id'), ('expires', EXPIRES_NAME)]

    def get_user_details(self, response):
        """Return user details from Facebook account"""
        return {USERNAME: response.get('username'),
                'email': response.get('email', ''),
                'fullname': response['name'],
                'first_name': response.get('first_name', ''),
                'last_name': response.get('last_name', '')}


class FacebookAuth(BaseOAuth2):
    """Facebook OAuth2 support"""
    AUTH_BACKEND = FacebookBackend
    RESPONSE_TYPE = None
    SCOPE_SEPARATOR = ','
    AUTHORIZATION_URL = 'https://www.facebook.com/dialog/oauth'
    SETTINGS_KEY_NAME = 'FACEBOOK_APP_ID'
    SETTINGS_SECRET_NAME = 'FACEBOOK_API_SECRET'

    def get_scope(self):
        return getattr(settings, 'FACEBOOK_EXTENDED_PERMISSIONS', [])

    def user_data(self, access_token):
        """Loads user data from service"""
        data = None
        url = FACEBOOK_ME + urlencode({'access_token': access_token})

        try:
            data = simplejson.load(urlopen(url))
            logger.debug('Found user data for token %s',
                         sanitize_log_data(access_token),
                         extra=dict(data=data))
        except ValueError:
            extra = {'access_token': sanitize_log_data(access_token)}
            logger.error('Could not load user data from Facebook.',
                         exc_info=True, extra=extra)
        return data

    def auth_complete(self, *args, **kwargs):
        """Completes loging process, must return user instance"""
        access_token = None
        expires = None

        if 'code' in self.data:
            url = 'https://graph.facebook.com/oauth/access_token?' + \
                  urlencode({'client_id': settings.FACEBOOK_APP_ID,
                             'redirect_uri': self.redirect_uri,
                             'client_secret': settings.FACEBOOK_API_SECRET,
                             'code': self.data['code']})
            response = cgi.parse_qs(urlopen(url).read())
            access_token = response['access_token'][0]
            if 'expires' in response:
                    expires = response['expires'][0]

        if 'signed_request' in self.data:
            response = load_signed_request(self.data.get('signed_request'))

            if response is not None:
                access_token = response.get('access_token') or response.get('oauth_token') \
                               or self.data.get('access_token')

                if 'expires' in response:
                    expires = response['expires']

        if access_token:
            data = self.user_data(access_token)
            if data is not None:
                if 'error' in data:
                    error = self.data.get('error') or 'unknown error'
                    raise ValueError('Authentication error: %s' % error)
                data['access_token'] = access_token
                # expires will not be part of response if offline access
                # premission was requested                
                if expires:
                    data['expires'] = expires
            kwargs.update({'response': data, self.AUTH_BACKEND.name: True})
            return authenticate(*args, **kwargs)
        else:
            error = self.data.get('error') or 'unknown error'
            raise ValueError('Authentication error: %s' % error)

    @classmethod
    def enabled(cls):
        """Return backend enabled status by checking basic settings"""
        return all(hasattr(settings, name) for name in ('FACEBOOK_APP_ID',
                                                        'FACEBOOK_API_SECRET'))


def base64_url_decode(data):
    data = data.encode(u'ascii')
    data += '=' * (4 - (len(data) % 4))
    return base64.urlsafe_b64decode(data)

def base64_url_encode(data):
    return base64.urlsafe_b64encode(data).rstrip('=')
    
def load_signed_request(signed_request):
    try:
        sig, payload = signed_request.split(u'.', 1)
        sig = base64_url_decode(sig)
        data = simplejson.loads(base64_url_decode(payload))

        expected_sig = hmac.new(
            settings.FACEBOOK_API_SECRET, msg=payload, digestmod=hashlib.sha256).digest()

        # allow the signed_request to function for upto 1 day
        if sig == expected_sig and \
                data[u'issued_at'] > (time.time() - 86400):
            return data 
    except ValueError, ex:
        pass # ignore if can't split on dot

# Backend definition
BACKENDS = {
    'facebook': FacebookAuth,
}
