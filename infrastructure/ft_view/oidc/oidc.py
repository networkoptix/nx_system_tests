# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import re
import secrets
from base64 import urlsafe_b64decode
from collections import OrderedDict
from functools import partial
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qsl
from urllib.parse import urlencode
from urllib.parse import urlparse
from urllib.request import Request
from urllib.request import urlopen


class _Handler(BaseHTTPRequestHandler):

    def __init__(self, *args, provider, store, **kwargs):
        self.provider: _Provider = provider
        self.store: _Store = store
        # It does its job during __init__(). That's why it's called last.
        super(_Handler, self).__init__(*args, **kwargs)

    def do_GET(self):
        host = self.headers['Host']
        if host is None:
            self.send_error(400, "Missing Host Header")
        callback_url = f'https://{host}/oidc/callback'
        if self.path.startswith('/oidc/callback?'):
            query = {k: v for k, v in parse_qsl(urlparse(self.path).query)}
            state = query.get('state', '')
            state_data = self.store.pop_state(state)
            if state_data is None:
                self.redirect_to_provider(callback_url)
            else:
                code = query.get('code', '')
                email = self.provider.introspect(code, callback_url)
                if email is None:
                    self.send_error(403)
                else:
                    self.redirect_with_authentication(email, state_data)
        elif self.path == '/oidc/validate':
            cookies = SimpleCookie(self.headers.get('Cookie'))
            if self.cookie_name() not in cookies:
                self.redirect_to_provider(callback_url)
            else:
                session_id = cookies[self.cookie_name()].value
                session_data = self.store.get_session(session_id)
                if session_data is None:
                    self.redirect_to_provider(callback_url)
                else:
                    self.send_authentication_success(session_data)
        else:
            self.send_error(404)

    def send_authentication_success(self, user):
        self.send_response(200)
        header_name = self.headers.get('OIDC-User-Header', 'User')
        self.send_header(header_name, user)
        self.send_header('Content-Length', '0')
        self.end_headers()

    def redirect_with_authentication(self, email, next_url):
        auth = secrets.token_urlsafe()
        self.store.save_session(auth, email)
        self.redirect(next_url, {self.cookie_name(): auth})

    def redirect_to_provider(self, callback_url):
        state = secrets.token_urlsafe()
        self.store.add_state(state, self.headers.get('X-Original-URI', '/'))
        url = self.provider.build_authenticate_url(state, callback_url)
        self.redirect(url)

    def redirect(self, location, cookies=None):
        status = self.headers.get('OIDC-Redirect-Status', '')
        status = re.fullmatch(r'[34]\d\d', status)
        status = int(status[0]) if status is not None else 302
        self.send_response(status)
        if cookies is not None:
            for name, value in cookies.items():
                cookie = SimpleCookie()
                cookie[name] = value
                cookie[name]['path'] = '/'
                cookie[name]['domain'] = self.headers.get('OIDC-Cookie-Domain', '')
                output = cookie[name].OutputString()
                self.send_header('Set-Cookie', output)
        header_name = self.headers.get('OIDC-Redirect-Header', 'Location')
        self.send_header(header_name, location)
        self.send_header('Content-Length', str(len(b'')))
        self.end_headers()
        self.wfile.write(b'')

    def cookie_name(self):
        return self.headers.get('OIDC-Cookie', 'auth')


class _Store:

    def __init__(self):
        self._sessions = OrderedDict()
        self._states = OrderedDict()

    def get_session(self, session_id):
        if session_id not in self._sessions:
            return None
        self._sessions.move_to_end(session_id)
        return self._sessions[session_id]

    def save_session(self, session_id, session_data):
        self._sessions[session_id] = session_data

    def add_state(self, state, param):
        self._states[state] = param

    def pop_state(self, state):
        return self._states.pop(state, None)


class _Provider:

    def __init__(self, email_domain, client_id, client_secret):
        self._email_domain = email_domain
        self._client_id = client_id
        self._client_secret = client_secret

    def build_authenticate_url(self, state, callback_url):
        params = {
            'client_id': self._client_id,
            'redirect_uri': callback_url,  # Required
            'response_type': 'code',
            'scope': 'email',
            'state': state,
            'hd': self._email_domain,
            }
        params = urlencode(params)
        return 'https://accounts.google.com/o/oauth2/v2/auth?' + params

    def introspect(self, code, callback_url):
        data = {
            'code': code,  # Must be there.
            'client_id': self._client_id,
            'client_secret': self._client_secret,
            'grant_type': 'authorization_code',
            'redirect_uri': callback_url,
            }
        data = json.dumps(data)
        data = data.encode()
        headers = {'Content-Type': 'application/json'}
        request = Request('https://oauth2.googleapis.com/token', data, headers)
        try:
            response = urlopen(request)
        except HTTPError as e:
            print(e.headers, e.read())
            return None
        if response.status != 200:
            return None
        response = response.read()
        response = json.loads(response)
        jwt = response['id_token']
        header, payload, signature = jwt.split('.')
        payload = urlsafe_b64decode(payload + '==')
        payload = json.loads(payload)
        email = payload['email']
        return email


if __name__ == '__main__':
    server = HTTPServer(('127.0.0.1', 8001), partial(
        _Handler,
        store=_Store(),
        provider=_Provider(
            'networkoptix.com',
            '209065389217-hdsd6cbhtpc4a0qkkh2ov2esrm6ff6rg.apps.googleusercontent.com',
            Path('~/.config/.secrets/us.nxft.dev-client-secret.txt').expanduser().read_text().strip(),
            ),
        ))
    server.serve_forever()
