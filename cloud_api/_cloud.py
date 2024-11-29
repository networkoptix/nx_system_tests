# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import base64
import hashlib
import hmac
import json
import logging
import random
import time
from contextlib import AbstractContextManager
from contextlib import contextmanager
from datetime import datetime
from datetime import timezone
from functools import lru_cache
from pathlib import Path
from pprint import pformat
from typing import Any
from typing import Collection
from typing import Literal
from typing import Mapping
from typing import NamedTuple
from typing import Optional
from typing import Sequence
from typing import Union
from urllib.parse import quote
from urllib.parse import unquote
from urllib.parse import urlencode
from urllib.parse import urlparse
from urllib.parse import urlunsplit
from uuid import UUID
from xml.etree import ElementTree

from _internal.cloud_account_credentials import _CLOUD_ACCOUNT_PASSWORD
from _internal.cloud_login_code_debug_credentials import LOGIN_CODE_DEBUG_API_PASSWORD
from _internal.cloud_login_code_debug_credentials import LOGIN_CODE_DEBUG_API_USERNAME
from cloud_api._http import HttpBasicAuthHandler
from cloud_api._http import HttpResponse
from cloud_api._http import _AuthHandler
from cloud_api._http import http_request
from cloud_api.channel_partners.organization import ChannelPartnerOrganizationData
from cloud_api.channel_partners.organization import OrganizationUser
from doubles.totp import TimeBasedOtp
from mediaserver_api import CannotObtainToken
from mediaserver_api import HttpBearerAuthHandler
from mediaserver_api import check_response_for_credentials

_logger = logging.getLogger(__name__)


class _CloudApiError(Exception):

    def __init__(self, response: HttpResponse, response_data: Optional[Mapping[str, Any]]):
        status_code = response.status_code
        if response_data is not None:
            reason = response_data.get('errorString', response.reason)
        else:
            reason = response.reason
        url = response.url
        super(_CloudApiError, self).__init__(f'[{status_code}] HTTP Error: {reason} url: {url}')


class _NotFound(_CloudApiError):
    pass


class Forbidden(_CloudApiError):
    pass


class _SystemInaccessible(Exception):
    pass


class BadRequest(_CloudApiError):
    pass


class _InternalServerError(_CloudApiError):
    pass


class _ServerBindInfo(NamedTuple):
    auth_key: str
    system_id: str


_HttpMethod = Literal['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
_HttpContent = Union[Mapping[str, Any], bytes, Sequence[Union[Mapping[str, Any], str]]]


class _RaiseStrategy:

    def __init__(self, hard_limit: int):
        self._hard_limit = hard_limit

    def should_raise(self, count_systems: int) -> bool:
        if count_systems >= self._hard_limit:
            return True
        return random.random() < count_systems / self._hard_limit


_raise_strategy = _RaiseStrategy(1000)


class _RemovalStrategy:

    def __init__(self, limit_sec: float):
        self._limit_sec = limit_sec

    def select(self, systems: Collection) -> Collection[Mapping]:
        outdated = [system for system in systems if self._is_outdated(system)]
        return random.sample(outdated, k=5) if len(outdated) >= 5 else outdated

    def _is_outdated(self, system: Mapping) -> bool:
        registration_timestamp = int(system['registrationTime']) / 1000
        registration_dt = datetime.fromtimestamp(registration_timestamp, timezone.utc)
        delta_sec = (datetime.now(timezone.utc) - registration_dt).total_seconds()
        return delta_sec > self._limit_sec


_removal_strategy = _RemovalStrategy(15 * 60)


class _HTTPClient:

    def __init__(
            self,
            hostname: str,
            auth_handler: _AuthHandler,
            cert_path: Optional[Path] = None,
            ):
        self._hostname = hostname
        self._ca_cert = cert_path
        self._auth_handler = auth_handler
        _logger.info("Trust CA cert: %r", self._ca_cert)

    def __repr__(self):
        return f'<{self.__class__.__name__} {self.username} at {self._hostname}>'

    @property
    def username(self) -> str:
        return self._auth_handler.username

    @property
    def password(self) -> str:
        return self._auth_handler.password

    def get_token(self) -> str:
        if not isinstance(self._auth_handler, HttpBearerAuthHandler):
            raise RuntimeError("Current authentication schema doesn't support tokens")
        return self._auth_handler.get_token()

    def request(
            self,
            method: _HttpMethod,
            path: str,
            params: Mapping[str, Any] = None,
            **kwargs,
            ) -> _HttpContent:
        path = path.lstrip('/')
        allow_redirects = kwargs.pop('allow_redirects', False)
        if params:
            # Server, which uses QUrlQuery doesn't support spaces, encoded as "+".
            # See https://doc.qt.io/qt-5/qurlquery.html#handling-of-spaces-and-plus.
            params = urlencode(params, quote_via=quote).encode('ascii')
            path = f'{path}?{params}'
        if 'json' in kwargs:
            content = kwargs['json']
        elif 'data' in kwargs:
            content = kwargs['data']
        else:
            content = None
        response = http_request(
            method=method,
            url=f'https://{self._hostname}/{path}',
            content=content,
            headers=kwargs.get('headers'),
            auth_handler=kwargs.get('auth_handler', self._auth_handler),
            ca_cert=self._ca_cert,
            allow_redirects=allow_redirects,
            )
        self._raise_for_status(response)
        response_data = response.json
        if response_data is None:
            _logger.warning("Non-JSON response:\n%s", response.content)
            return response.content
        check_response_for_credentials(response_data, path)
        return response_data

    @staticmethod
    def _raise_for_status(response: HttpResponse):
        response_data = response.json
        if response.status_code == 500:
            raise _InternalServerError(response, response_data)
        if response.status_code == 404:
            raise _NotFound(response, response_data)
        if response.status_code == 403:
            raise Forbidden(response, response_data)
        if response.status_code == 400:
            raise BadRequest(response, response_data)
        if response.status_code > 400:
            raise _CloudApiError(response, response_data)
        if response.status_code < 300:
            if not isinstance(response_data, Sequence):
                result_code = response_data.get('resultCode') if response_data is not None else None
                if result_code not in ['OK', 'ok', None]:
                    raise _CloudApiError(response, response_data)

    def do_get(self, path: str, params: Mapping[str, Any] = None, **kwargs) -> _HttpContent:
        # Adding "do_" prefix as PyCharm would find usages of dict.get() without it.
        params_str = pformat(params, indent=4)
        if '\n' in params_str or len(params_str) > 60:
            params_str = '\n' + params_str
        _logger.debug('GET %s, params: %s', path, params_str)
        assert 'data' not in kwargs
        assert 'json' not in kwargs
        return self.request('GET', path, params=params, **kwargs)

    def do_post(
            self,
            path: str,
            data: Union[Collection[str], Mapping[str, Any]],
            **kwargs,
            ) -> _HttpContent:
        return self._make_json_request('POST', path, data, **kwargs)

    def do_patch(
            self,
            path: str,
            data: Collection[str] | Mapping[str, Any],
            **kwargs,
            ) -> _HttpContent:
        return self._make_json_request('PATCH', path, data, **kwargs)

    def _make_json_request(
            self,
            method: _HttpMethod,
            path: str,
            data: Mapping[str, Any],
            **kwargs,
            ) -> _HttpContent:
        data_str = json.dumps(data)
        if len(data_str) > 60:
            data_str = '\n' + json.dumps(data, indent=4)
        _logger.debug('%s %s, payload:\n%s', method, path, data_str)
        return self.request(method, path, json=data, **kwargs)

    def do_put(
            self,
            path: str,
            data: Union[Mapping[str, Any], Sequence[Mapping[str, Any]]],
            **kwargs,
            ) -> _HttpContent:
        return self._make_json_request('PUT', path, data, **kwargs)

    def do_delete(self, path: str, **kwargs) -> _HttpContent:
        return self.request('DELETE', path, **kwargs)


class _CloudPortalApi:
    """Cloud Portal API documentation: https://cloud-test.hdw.mx/swagger/."""

    def __init__(
            self,
            http_client: _HTTPClient,
            ):
        self._http = http_client

    def register_user(self, email: str, password: str):
        self._http.do_post(
            'api/account/register',
            {
                'email': email,
                'password': password,
                'first_name': 'FT Account',
                'last_name': 'Some long last name for test Cloud account',  # To see if it fits in forms
                'subscribe': False,
                },
            auth_handler=None,  # Avoid authentication
            )

    def delete_account(self) -> None:
        self._http.do_post('api/account/delete', {'password': self._http.password})

    def get_activation_code(
            self, target_email: str, headers: Optional[Mapping[str, Any]] = None) -> str:
        timeout = 5
        started_at = time.monotonic()
        while True:
            response = self._http.do_post(
                'api/robot/get_code',
                {
                    'email': target_email,
                    'type': 'activate_account',
                    },
                headers=headers,
                auth_handler=None,  # Avoid authentication
                )
            code = response['code']
            if code != 'Does not exist':
                # An equals sign at the end of an encoded value can be escaped as "%3D".
                return unquote(code)
            if time.monotonic() - started_at > timeout:
                raise RuntimeError(
                    f"Activation code for {target_email} not found in {timeout} sec")
            time.sleep(0.5)

    def get_cloud_customization_name(self) -> str:
        response = self._http.do_get(
            '/api/utils/customization',
            auth_handler=None,  # Avoid authentication
            )
        return response['name']

    def disconnect_system(self, system_id: str) -> None:
        self._http.do_post('api/systems/disconnect', {
            'email': self._http.username,
            'password': self._http.password,
            'system_id': system_id,
            })

    def disable_2fa(self, code: str) -> None:
        self._http.do_post('api/account/security', {
            'action': 'deactivate',
            'mfaCode': code,
            })


class _CDBApi:
    """CloudDB API documentation: https://cloud-test.hdw.mx/cdb/docs/api/v1/swagger/index.html."""

    def __init__(
            self,
            http_client: _HTTPClient,
            ):
        self._http = http_client

    def get_user_info(self) -> '_UserInfo':
        response = self._http.do_get('cdb/account/get')
        return _UserInfo(response)

    def get_self_info(self) -> '_UserInfo':
        response = self._http.do_get('cdb/account/self')
        return _UserInfo(response)

    def get_status(self, user_email: str) -> _HttpContent:
        return self._http.do_get(
            f'cdb/account/{user_email}/status',
            auth_handler=None,  # Avoid authentication
            )

    def get_temporary_credentials(self) -> tuple[str, str]:
        response = self._http.request(
            method='POST',
            path='cdb/account/createTemporaryCredentials',
            json={"type": "short"},
            )
        return response['login'], response['password']

    def get_user_info_request_with_credentials(self, login: str, password: str) -> _HttpContent:
        # TODO: Refactor to avoid usage of protected fields of _HttpClient.
        response = http_request(
            method='GET',
            url=f'https://{self._http._hostname}/cdb/account/get',
            auth_handler=HttpBasicAuthHandler(login, password),
            ca_cert=self._http._ca_cert,
            )
        self._http._raise_for_status(response)
        return response.json

    def rename_user(self, new_name: str):
        self._http.do_post('cdb/account/update', {'fullName': new_name})

    def delete_user(self):
        self._http.do_delete('cdb/account/self')

    def register_user(self, email: str, password: str, customization_name: str):
        self._http.do_post(
            'cdb/account/register',
            {
                'email': email,
                'password': password,
                'fullName': 'FT Account CDB Test',
                'customization': customization_name,
                'settings': {'security': {'httpDigestAuthEnabled': True}},
                },
            auth_handler=None,  # Avoid authentication
            )

    def request_password_reset(self, email: str, customization_name: str):
        self._http.do_post('/cdb/account/resetPassword', {
            'email': email,
            'customization': customization_name,
            })

    def resend_activation_code(self, email: str):
        response = self._http.do_post('cdb/account/reactivate', {'email': email})
        if response != {'code': ''}:
            raise RuntimeError(f"Reactivation request failed: {response}")

    def activate_user(self, email: str, activation_code: str):
        response = self._http.do_post(
            'cdb/account/activate',
            {
                'code': activation_code,
                },
            auth_handler=None,  # Avoid authentication
            )
        if response.get('email') != email:
            raise RuntimeError(f"Activation not for {email}: {response}")

    def update_user_customization(self, customization: str):
        self._http.do_post('cdb/account/update', {'customization': customization})

    def bind_only(self, system_name: str, customization_name: str) -> _ServerBindInfo:
        response = self._http.do_post('cdb/systems/bind', {
            'name': system_name,
            'customization': customization_name,
            })
        return _ServerBindInfo(response['authKey'], response['id'])

    def list_health_history(self, system_id: UUID) -> Collection[str]:
        return self._http.do_get(f'cdb/systems/{system_id}/health-history')['events']

    def get_data_sync_settings(self, system_id: UUID) -> _HttpContent:
        return self._http.do_get(f'cdb/systems/{system_id}/data-sync-settings')

    def validate_key(self, system_id: UUID, data: Mapping[str, Any]) -> _HttpContent:
        return self._http.do_post(f'cdb/systems/{system_id}/signature/validate', data)

    def merge_systems(self, master_system_id: UUID, data: Mapping[str, Any]):
        try:
            self._http.do_post(f'cdb/systems/{master_system_id}/merged_systems/', data)
        except Forbidden:
            _logger.info(
                "403 HTTP Error appears in response. "
                "However, the merge has been completed successfully. "
                "See: https://networkoptix.atlassian.net/browse/CLOUD-14463")

    def list_attributes(self, system_id: UUID) -> Sequence[Mapping[str, str]]:
        return self._http.do_get(f'cdb/systems/{system_id}/attributes')

    def add_attribute(self, system_id: UUID, name: str, value: str) -> None:
        self._http.do_post(
            f'cdb/systems/{system_id}/attributes/{name}',
            {'name': name, 'value': value},
            )

    def update_attributes(self, system_id: UUID, attributes: Sequence[Mapping[str, str]]) -> None:
        self._http.do_put(
            f'cdb/systems/{system_id}/attributes',
            attributes,
            )

    def update_attribute(self, system_id: UUID, name: str, value: str) -> None:
        self._http.do_put(
            f'cdb/systems/{system_id}/attributes/{name}',
            {'name': name, 'value': value},
            )

    def remove_attribute(self, system_id: UUID, attribute_name: str) -> None:
        self._http.do_delete(f'cdb/systems/{system_id}/attributes/{attribute_name}')

    def get_system(self, system_id: UUID) -> Optional[_HttpContent]:
        return self._http.do_get(f'cdb/systems/{system_id}')

    def obtain_token(self, username: str, password: str, system_id: Optional[str]) -> str:
        data = {
            'grant_type': 'password',
            'response_type': 'token',
            'client_id': 'FT',
            'username': username,
            'password': password,
            }
        if system_id is not None:
            data['scope'] = f'cloudSystemId={system_id}'
        try:
            data = self._http.do_post(
                'cdb/oauth2/token',
                data,
                auth_handler=None,  # To prevent circular method calls
                )
        except Forbidden:
            raise CannotObtainToken()
        return data['access_token']

    def verify_token_with_totp(self, totp_code: str) -> None:
        token = self._http.get_token()
        self._http.do_get(
            f'cdb/account/self/2fa/totp/key/{totp_code}?token={token}',
            auth_handler=None,  # The endpoint doesn't require authentication
            )

    def list_system_users(self, system_id: UUID) -> Collection['_SystemUserInfo']:
        return [_SystemUserInfo(raw) for raw in self._http.do_get(f'cdb/systems/{system_id}/users')]

    def list_system_user_attributes(self, system_id: UUID, user_email: str) -> Collection[_HttpContent]:
        return self._http.do_get(f'cdb/systems/{system_id}/users/{user_email}/attributes')

    def create_batch(
            self,
            system_ids: Collection[UUID],
            user_emails: Collection[str],
            role_ids: Collection[UUID],
            attributes: Mapping[str, str]) -> _HttpContent:
        system_ids_str = [str(i) for i in system_ids]
        role_ids_str = [str(i) for i in role_ids]
        data = {
            "items": [{
                "users": user_emails,
                "systems": system_ids_str,
                "roleIds": role_ids_str,
                "attributes": attributes,
                }],
            }
        return self._http.do_post('cdb/systems/users/batch', data)

    def get_batch_status(self, batch_id: str) -> str:
        response = self._http.do_get(f'cdb/systems/users/batch/{batch_id}/state')
        return response['status']

    def get_batch_error(self, batch_id: str) -> _HttpContent:
        return self._http.do_get(f'cdb/systems/users/batch/{batch_id}/error')

    def add_system_user_attributes(
            self,
            system_id: UUID,
            user_email: str,
            attributes: Sequence[Mapping[str, str]],
            ) -> Collection[_HttpContent]:
        return self._http.do_put(
            f'cdb/systems/{system_id}/users/{user_email}/attributes',
            attributes,
            )

    def update_system_user_attribute(
            self, system_id: UUID, user_email: str, name: str, value: str) -> None:
        self._http.do_put(
            f'cdb/systems/{system_id}/users/{user_email}/attributes/{name}',
            {'name': name, 'value': value},
            )

    def delete_system_user_attribute(self, system_id: UUID, user_email: str, name: str) -> None:
        self._http.do_delete(
            f'cdb/systems/{system_id}/users/{user_email}/attributes/{name}')

    def share_system(self, system_id: UUID, user_email: str, user_groups: Collection[UUID]):
        self._http.do_post(f'cdb/v0/systems/{system_id}/users', {
            'accountEmail': user_email,
            'roleIds': [str(role_uid) for role_uid in user_groups],
            })

    def stop_sharing_system(self, system_id: UUID, user_email: str) -> None:
        self._http.do_delete(f'cdb/systems/{system_id}/users/{user_email}')

    def get_security_settings(self) -> _HttpContent:
        return self._http.do_get('cdb/account/self/settings/security')

    def set_session_lifetime(self, lifetime_sec: int, password: str) -> None:
        self._http.do_put('cdb/account/self/settings/security', {
            'authSessionLifetime': lifetime_sec,
            'password': password,
            })

    def get_systems(self) -> Collection[Mapping[Any, Any]]:
        response = self._http.do_get('cdb/systems/get')
        return [system for system in response['systems']]

    def remove_system(self, system_id: str):
        try:
            self._http.do_delete(f'cdb/systems/{system_id}')
        except Forbidden:
            raise _SystemInaccessible(f'System {system_id} is inaccessible or removed')

    def rename_system(self, system_id: UUID, new_name: str):
        self._http.do_put(f'cdb/systems/{system_id}', {'name': new_name})

    def offer_system(self, system_id: UUID, target_email: str, comment: str) -> None:
        # Wrong schema in CDB API Swagger for data. The format below is working.
        # See: https://networkoptix.atlassian.net/browse/CB-2539
        data = {
            "toAccount": target_email,
            "systemId": str(system_id),
            "comment": comment,
            }
        self._http.do_post(f'cdb/v0/systems/{system_id}/offer', data)

    def revoke_system_offer(self, system_id: UUID) -> None:
        self._http.do_delete(f'cdb/v0/systems/{system_id}/offer')

    def list_system_offers(self) -> Collection[_HttpContent]:
        return self._http.do_get('cdb/v0/system-offers')

    def accept_system_offer(self, system_id: UUID) -> None:
        self._http.do_post(f'cdb/v0/system-offers/{system_id}/accept', {})

    def reject_system_offer(self, system_id: UUID) -> None:
        self._http.do_post(f'cdb/v0/system-offers/{system_id}/reject', {})


class CloudAccount:

    def __init__(
            self,
            hostname: str,
            user_email: str,
            cert_path: Optional[Path] = None,
            ):
        self._hostname = hostname
        self._ca_cert = cert_path
        _logger.info("Trust CA cert: %r", self._ca_cert)
        token_provider = _CloudTokenProvider(self)
        self._auth_handler = HttpBearerAuthHandler(
            user_email, _CLOUD_ACCOUNT_PASSWORD, token_provider)
        self._http_client = _HTTPClient(self._hostname, self._auth_handler, cert_path)
        self._cdb_api = _CDBApi(self._http_client)
        self._portal_api = _CloudPortalApi(self._http_client)
        self._totp_generator: Optional[TimeBasedOtp] = None

    @property
    def user_email(self) -> str:
        return self._auth_handler.username

    @property
    def password(self) -> str:
        return self._auth_handler.password

    def make_auth_handler(self, system_id: Optional[str] = None) -> 'HttpBearerAuthHandler':
        token_provider = _CloudTokenProvider(self, system_id)
        return HttpBearerAuthHandler(self.user_email, self.password, token_provider)

    def get_activation_code(self, headers: Optional[Mapping[str, Any]] = None) -> str:
        return self._portal_api.get_activation_code(self.user_email, headers)

    def get_privileged_auth_headers(self) -> Mapping[str, Any]:
        # Several API endpoints are created specifically for automated testing purposes.
        # These endpoints are available to everyone on Cloud instances with DEBUG mode enabled.
        # However, if DEBUG mode is disabled, a special hard-coded account must be used.
        # Passing the Authorization header for the privileged account is not enough.
        # A CSRF token and additional verification headers must be used.
        code = self._get_authentication_code(LOGIN_CODE_DEBUG_API_USERNAME, LOGIN_CODE_DEBUG_API_PASSWORD)
        response = http_request(
            method='POST',
            url=f'https://{self._hostname}/api/account/loginCode',
            content={'code': code},
            ca_cert=self._ca_cert,
            )
        cookies: Collection[str] = response.headers.get_all('Set-Cookie')
        [csrf_cookie] = [cookie for cookie in cookies if cookie.startswith('csrftoken=')]
        [csrf_pair, *_] = csrf_cookie.split(';', maxsplit=1)
        [_, csrftoken] = csrf_pair.split('=', maxsplit=1)
        return {
            'Cookie': '; '.join(cookies),
            'Referer': f'https://{self._hostname}/authorize',
            'X-CSRFToken': csrftoken,
            }

    def set_totp_generator(self, totp_generator: 'TimeBasedOtp') -> None:
        self._totp_generator = totp_generator
        # Verify the currently used authentication token with TOTP
        # to use it with two-factor authentication enabled.
        one_time_password = self._totp_generator.generate_otp()
        self._cdb_api.verify_token_with_totp(one_time_password)

    def _get_authentication_code(self, email: str, password: str) -> str:
        response = self._http_client.do_post(
            'oauth/authenticate',
            {
                'client_id': 'FT',
                'grant_type': 'password',
                'response_type': 'code',
                'email': email,
                'password': password,
                'redirect_uri': '',
                },
            auth_handler=None,  # Avoid request authentication
            )
        return response['code']

    def activate_user(self, activation_code: str):
        self._cdb_api.activate_user(self.user_email, activation_code)

    def register_user(self):
        self._portal_api.register_user(self.user_email, self.password)

    def set_password(self, password: str):
        self._auth_handler.password = password

    def get_services_hosts(self) -> Sequence[str]:
        response = self._http_client.do_get('discovery/v2/cloud_modules.xml')
        root = ElementTree.fromstring(response)
        relay_node = root.find('.//set[@resName="relay"]')
        if relay_node is not None:
            relay_url = relay_node.attrib['resValue']
            relay_host = urlparse(relay_url).hostname
        else:
            # The relay node may not be present in the discovery response,
            # in which case the default pattern should be used.
            relay_host = f'relay.{self._hostname}'
        mediator_node = root.find('.//set[@resName="hpm.tcpUrl"]')
        if mediator_node is None:
            raise RuntimeError("Unable to find Mediator service hostname")
        mediator_url = mediator_node.attrib['resValue']
        mediator_host = urlparse(mediator_url).hostname
        services = [relay_host, mediator_host]
        # The Prod and Stage Cloud instances have multiple mediator and relay services.
        # The response to /discovery/v2/cloud_modules.xml typically includes only one service URL,
        # often the proxy. However, VMS uses the URL of the closest available service.
        if self._hostname in ('nxvms.com', 'stage.nxvms.com'):
            # Note that these hostnames must be allowed by the iptables rules.
            services.extend([
                'relay-ny2.vmsproxy.com',
                'dp-ny-3.vmsproxy.com',
                'dp-ny-4.vmsproxy.com',
                'dp-ny-4.vmsproxy.com',
                'relay-la.vmsproxy.com',
                'dp-la-2.vmsproxy.com',
                'relay-chi.vmsproxy.com',
                'relay-mia.vmsproxy.com',
                'relay-dp-dal-1.vmsproxy.com',
                'relay-dp-ash-1.vmsproxy.com',
                'relay-dp-sea-1.vmsproxy.com',
                'ap-southeast-1.mediator.vmsproxy.com',
                'ap-southeast-2.mediator.vmsproxy.com',
                'eu-central-1.mediator.vmsproxy.com',
                'me-south-1.mediator.vmsproxy.com',
                'us-east-1.mediator.vmsproxy.com',
                'us-east-2.mediator.vmsproxy.com',
                'us-west-1.mediator.vmsproxy.com',
                'us-west-1.mediator.vmsproxy.hdw.mx',
                'us-east-1.mediator.vmsproxy.hdw.mx',
                ])
        return services

    def __repr__(self):
        return f'<{self.__class__.__name__} {self.user_email} at {self._hostname}>'

    def delete(self) -> None:
        self._portal_api.delete_account()

    def get_user_info(self) -> '_UserInfo':
        return self._cdb_api.get_user_info()

    def get_self_info(self) -> '_UserInfo':
        return self._cdb_api.get_self_info()

    def _get_status(self) -> _HttpContent:
        return self._cdb_api.get_status(self.user_email)

    def get_temporary_credentials(self) -> tuple[str, str]:
        return self._cdb_api.get_temporary_credentials()

    def get_user_info_request_with_credentials(self, login: str, password: str) -> _HttpContent:
        return self._cdb_api.get_user_info_request_with_credentials(login, password)

    def get_status_code(self) -> str:
        return self._get_status()['statusCode']

    def rename_user(self, new_name: str):
        self._cdb_api.rename_user(new_name)

    def delete_user(self):
        self._cdb_api.delete_user()

    def user_is_accessible(self):
        try:
            self._get_status()
        except _NotFound:
            return False
        else:
            return True

    def register_user_cdb(self):
        customization_name = self._portal_api.get_cloud_customization_name()
        self._cdb_api.register_user(self.user_email, self.password, customization_name)

    def request_password_reset(self):
        customization_name = self._portal_api.get_cloud_customization_name()
        self._cdb_api.request_password_reset(self.user_email, customization_name)

    def resend_activation_code(self):
        self._cdb_api.resend_activation_code(self.user_email)

    def set_user_customization(self, customization: str):
        self._cdb_api.update_user_customization(customization)
        user_info = self.get_user_info()
        if user_info.get_customization() != customization:
            raise RuntimeError(f"Failed to set customization: {user_info.get_raw_data()}")
        _logger.info(
            'Account with Email %r belongs to customization %r',
            self.user_email, customization)

    def bind_system(self, system_name: str) -> _ServerBindInfo:
        self.remove_outdated_systems()
        return self._bind_only(system_name)

    def _bind_only(self, system_name: str) -> _ServerBindInfo:
        customization_name = self._portal_api.get_cloud_customization_name()
        return self._cdb_api.bind_only(system_name, customization_name)

    def list_health_history(self, system_id: UUID) -> Collection[str]:
        return self._cdb_api.list_health_history(system_id)

    def get_data_sync_settings(self, system_id: UUID) -> _HttpContent:
        return self._cdb_api.get_data_sync_settings(system_id)

    def auth_key_is_valid(self, system_id: UUID, auth_key: str) -> bool:
        message = "Some text"
        signature = _compose_signature(auth_key, message).decode()
        data = {'message': message, 'signature': signature}
        try:
            self._cdb_api.validate_key(system_id, data)
        except BadRequest:
            return False
        return True

    def merge_systems(self, master_system_id: UUID, slave_system_id: str):
        master_token = self.obtain_token(self.user_email, self.password, str(master_system_id))
        slave_token = self.obtain_token(self.user_email, self.password, str(slave_system_id))
        data = {
            "systemId": str(slave_system_id),
            "masterSystemAccessToken": master_token,
            "slaveSystemAccessToken": slave_token,
            }
        self._cdb_api.merge_systems(master_system_id, data)

    def list_attributes(self, system_id: UUID) -> Sequence[Mapping[str, str]]:
        return self._cdb_api.list_attributes(system_id)

    def add_attribute(self, system_id: UUID, name: str, value: str) -> None:
        self._cdb_api.add_attribute(system_id, name, value)

    def update_attributes(self, system_id: UUID, attributes: Sequence[Mapping[str, str]]) -> None:
        self._cdb_api.update_attributes(system_id, attributes)

    def update_attribute(self, system_id: UUID, name: str, value: str) -> None:
        self._cdb_api.update_attribute(system_id, name, value)

    def remove_attribute(self, system_id: UUID, attribute_name: str) -> None:
        self._cdb_api.remove_attribute(system_id, attribute_name)

    def get_system(self, system_id: UUID) -> Optional[_HttpContent]:
        try:
            return self._cdb_api.get_system(system_id)
        except _NotFound:
            return None

    def can_access_system(self, system_id: UUID) -> bool:
        try:
            return self.get_system(system_id) is not None
        except Forbidden:
            return False

    def obtain_token(self, username: str, password: str, system_id: Optional[str] = None) -> str:
        return self._cdb_api.obtain_token(username, password, system_id)

    def list_system_users(self, system_id: UUID) -> Collection['_SystemUserInfo']:
        return self._cdb_api.list_system_users(system_id)

    def list_system_user_attributes(self, system_id: UUID) -> Collection[_HttpContent]:
        return self._cdb_api.list_system_user_attributes(system_id, self.user_email)

    def get_system_user_by_email(self, system_id: UUID, user_email: str) -> '_SystemUserInfo':
        for user in self.list_system_users(system_id):
            if user.get_email() == user_email:
                return user
        raise RuntimeError(
            f"No user with email {user_email} found among users of system {system_id}")

    def create_batch(
            self,
            system_ids: Collection[UUID],
            user_emails: Collection[str],
            role_ids: Collection[UUID],
            attributes: Mapping[str, str]):
        response = self._cdb_api.create_batch(system_ids, user_emails, role_ids, attributes)
        batch_id = response['batchId']
        if not self._batch_performed_successfully(batch_id):
            error_description = self._get_batch_error_info_description(batch_id)
            raise BatchRequestFailed(error_description)

    def _batch_performed_successfully(self, batch_id: str) -> bool:
        started_at = time.monotonic()
        timeout = 5
        while True:
            status = self._cdb_api.get_batch_status(batch_id)
            if status == 'success':
                return True
            elif status == 'failure':
                return False
            elif status == 'inProgress':
                _logger.info(f"Batch {batch_id} is in `{status}`. Retrying after a small delay")
            else:
                raise RuntimeError(f'Batch {batch_id} has an unknown status: {status}')
            if time.monotonic() - started_at > timeout:
                raise RuntimeError(f"Batch {batch_id} in pending status for `{timeout}` seconds")
            time.sleep(1)

    def _get_batch_error_info_description(self, batch_id: str) -> str:
        error = self._cdb_api.get_batch_error(batch_id)['uncommitted']
        if len(error) == 0:
            return ''
        [error_attributes] = error
        return error_attributes['description']

    def add_system_user_attributes(
            self,
            system_id: UUID,
            attributes: Sequence[Mapping[str, str]],
            ) -> Collection[_HttpContent]:
        return self._cdb_api.add_system_user_attributes(system_id, self.user_email, attributes)

    def update_system_user_attribute(self, system_id: UUID, name: str, value: str) -> None:
        self._cdb_api.update_system_user_attribute(system_id, self.user_email, name, value)

    def delete_system_user_attribute(self, system_id: UUID, name: str) -> None:
        self._cdb_api.delete_system_user_attribute(system_id, self.user_email, name)

    def offer_system(self, system_id: UUID, target_email: str, comment: str) -> None:
        self._cdb_api.offer_system(system_id, target_email, comment)

    def list_system_offers(self) -> Collection['_SystemOfferInfo']:
        return [_SystemOfferInfo(r) for r in self._cdb_api.list_system_offers()]

    def accept_system_offer(self, system_id: UUID) -> None:
        self._cdb_api.accept_system_offer(system_id)

    def revoke_system_offer(self, system_id: UUID) -> None:
        self._cdb_api.revoke_system_offer(system_id)

    def reject_system_offer(self, system_id: UUID) -> None:
        self._cdb_api.reject_system_offer(system_id)

    def share_system(self, system_id: UUID, user_email, user_groups: Collection[UUID]):
        self._cdb_api.share_system(system_id, user_email, user_groups)

    def stop_sharing_system(self, system_id: UUID, user_email: str) -> None:
        self._cdb_api.stop_sharing_system(system_id, user_email)

    def get_security_settings(self) -> _HttpContent:
        return self._cdb_api.get_security_settings()

    def set_session_lifetime(self, lifetime_sec: int):
        self._cdb_api.set_session_lifetime(lifetime_sec, self.password)

    def remove_outdated_systems(self):
        systems = self._get_offline_systems()
        _logger.info('Found outdated systems: %s', len(systems))
        to_remove = _removal_strategy.select(systems)
        for system in to_remove:
            _logger.info('Remove outdated cloud system %r', system)
            try:
                self._remove_system(system['id'])
            except _SystemInaccessible as err:
                _logger.info(
                    "Can't remove system %s. It is not a problem, could be suppressed.",
                    system['id'], exc_info=err)
            except _CloudApiError as err:
                if _raise_strategy.should_raise(len(systems)):
                    raise RuntimeError(
                        f"Too many outdated cloud systems ({len(systems)}), please remove them.")
                _logger.error("Error due remove system %s: %s", system['id'], str(err))

    def get_systems(self) -> Collection[Mapping[Any, Any]]:
        return self._cdb_api.get_systems()

    def list_system_ids(self) -> Collection[str]:
        return [system['id'] for system in self._cdb_api.get_systems()]

    def _get_offline_systems(self) -> Collection[Mapping[Any, Any]]:
        all_systems = self.get_systems()
        return [system for system in all_systems if system['stateOfHealth'] == 'offline']

    def disconnect_system(self, system_id: str):
        self._portal_api.disconnect_system(system_id)

    def _remove_system(self, system_id: str):
        self._cdb_api.remove_system(system_id)

    def rename_system(self, system_id: UUID, new_name: str):
        self._cdb_api.rename_system(system_id, new_name)

    def disable_2fa(self) -> None:
        one_time_password = self._totp_generator.generate_otp()
        self._portal_api.disable_2fa(one_time_password)

    @lru_cache()
    def make_channel_partner_api(self) -> '_ChannelPartnerApi':
        return _ChannelPartnerApi(self._http_client)


def _compose_signature(auth_key: str, message: str) -> bytes:
    # According to schema the signature has to be in a format like
    # SIGNATURE = base64(hmacSha256(cloudSystemAuthKey, message))
    hmac_code = hmac.new(
        key=auth_key.encode(),
        msg=message.encode(),
        digestmod=hashlib.sha256).digest()
    return base64.b64encode(hmac_code)


class _UserInfo:

    def __init__(self, info_struct: Mapping[str, Any]):
        self._info_struct = info_struct

    def get_id(self) -> UUID:
        return UUID(self._info_struct['id'])

    def get_customization(self) -> str:
        return self._info_struct['customization']

    def get_full_name(self) -> str:
        return self._info_struct['fullName']

    def get_raw_data(self) -> Mapping[str, Any]:
        return self._info_struct

    def account_2fa_is_enabled(self) -> bool:
        return self._info_struct['account2faEnabled']


class _SystemUserInfo:

    def __init__(self, info_struct: _HttpContent):
        self._info_struct = info_struct

    def get_id(self) -> UUID:
        return UUID(self._info_struct['id'])

    def get_email(self) -> str:
        return self._info_struct['accountEmail']

    def get_role(self) -> str:
        return self._info_struct['accessRole']

    def get_raw_data(self) -> Mapping[str, Any]:
        return self._info_struct


class _SystemOfferInfo:

    def __init__(self, info_struct: _HttpContent):
        self._info_struct = info_struct

    def from_account(self) -> str:
        return self._info_struct['fromAccount']

    def to_account(self) -> str:
        return self._info_struct['toAccount']

    def system_id(self) -> UUID:
        return UUID(self._info_struct['systemId'])

    def comment(self) -> str:
        return self._info_struct['comment']

    def status(self) -> str:
        return self._info_struct['status']


class _CloudTokenProvider:

    def __init__(self, account: CloudAccount, system_id: Optional[str] = None):
        self._account = account
        self._system_id = system_id

    def obtain_token(self, username: str, password: str) -> str:
        return self._account.obtain_token(username, password, self._system_id)

    @staticmethod
    def must_be_subsumed():
        # For cloud systems a token must be obtained from the cloud
        # even if a slave system is also a cloud system, since the slave
        # and a master have different cloud system IDs that are used to obtain token.
        return True


class _ChannelPartnerApi:
    """Channel Partner API documentation: https://test.ft-cloud.hdw.mx/partners/."""

    def __init__(self, http_client: _HTTPClient):
        self._http = http_client

    def grant_channel_partner_access(self, user_email: str) -> Sequence[_HttpContent]:
        return self._http.do_post('partners/api/v2/internal/grant_access/', {'email': user_email})

    def list_available_roles(self) -> 'Collection[ChannelPartnerRole]':
        response = self._http.do_get('partners/api/v2/channel_partner_roles')
        return [ChannelPartnerRole(role) for role in response]

    def list_channel_partner_users(self, main_cp_id: UUID) -> 'Collection[_ChannelPartnerUserInfo]':
        raw = self._http.do_get(f'partners/api/v2/channel_partners/{main_cp_id}/users/')
        return [_ChannelPartnerUserInfo(user) for user in raw]

    def get_subpartner_by_email(
            self, main_cp_id: UUID, target_email: str) -> '_ChannelPartnerUserInfo':
        raw = self._http.do_get(
            f'partners/api/v2/channel_partners/{main_cp_id}/users/{target_email}/')
        return _ChannelPartnerUserInfo(raw)

    def _get_paginated_result(self, initial_url: str) -> Sequence[_HttpContent]:
        response = self._http.do_get(initial_url)
        result = response['results']
        while True:
            next_url = response['next']
            if next_url is None:
                break
            parsed_url = urlparse(next_url)
            relative_url = urlunsplit(('', '', parsed_url.path, parsed_url.query, ''))
            response = self._http.do_get(relative_url)
            result += response['results']
        if len(result) != response['count']:
            raise RuntimeError(
                f"Total entries found: {len(result)}; Response.count is {response['count']}")
        return result

    def update_channel_partner_user(
            self,
            main_cp_id: UUID,
            target_email: str,
            role_id: UUID,
            title: Optional[str] = None,
            attributes: Optional[Mapping[str, str]] = None,
            ) -> None:
        data = {"email": target_email, "roleId": str(role_id)}
        if title is not None:
            data['title'] = title
        if attributes is not None:
            data['attributes'] = attributes
        self._http.do_post(f'partners/api/v2/channel_partners/{main_cp_id}/users/', data)

    def get_paginated_subpartners_list(
            self, main_cp_id: UUID, ordering: str) -> 'Sequence[_ChannelPartnerUserInfo]':
        result = self._get_paginated_result(
            f'partners/api/v2/channel_partners/{main_cp_id}/users/paginated/?ordering={ordering}')
        return [_ChannelPartnerUserInfo(user) for user in result]

    def list_subpartners_emails(self, cp_id: UUID) -> Collection[str]:
        return [partner.get_email() for partner in self.list_channel_partner_users(cp_id)]

    def get_current_user_record(self, main_cp_id: UUID) -> '_ChannelPartnerUserInfo':
        raw = self._http.do_get(f'partners/api/v2/channel_partners/{main_cp_id}/users/self/')
        return _ChannelPartnerUserInfo(raw)

    def delete_subpartner(self, main_cp_id: UUID, target_email: str) -> None:
        self._http.do_delete(f'partners/api/v2/channel_partners/{main_cp_id}/users/{target_email}/')

    def bulk_delete_users(self, main_cp_id: UUID, emails: Collection[str]) -> None:
        self._http.do_post(
            f'partners/api/v2/channel_partners/{main_cp_id}/users/bulk_delete/', emails)

    def list_channel_partners(self) -> Collection['_ChannelPartnerUserInfo']:
        result = self._http.do_get('partners/api/v2/channel_partners/')
        return [_ChannelPartnerUserInfo(user) for user in result['results']]

    def create_channel_partner(
            self, name: str, parent_partner_id: UUID, account_email: str) -> '_ChannelPartnerUserInfo':
        data = {
            "name": name,
            "parentChannelPartner": str(parent_partner_id),
            "attributes": {
                "additionalProp1": "string",
                "additionalProp2": "string",
                "additionalProp3": "string",
                },
            "monthlyAdditionalServiceLimit": 0,
            "supportInformation": {
                "sites": [],
                "phones": [],
                "emails": [],
                "custom": [],
                },
            "firstAdminEmail": account_email,
            }
        partner = self._http.do_post('partners/api/v2/channel_partners/', data)
        return _ChannelPartnerUserInfo(partner)

    def _list_sub_channel_partners(self, cp_id: UUID) -> Collection['_ChannelPartnerUserInfo']:
        result = self._get_paginated_result(
            f'partners/api/v2/channel_partners/{cp_id}/sub_channel_partners/')
        return [_ChannelPartnerUserInfo(user) for user in result]

    def get_channel_partner(self, cp_id: UUID) -> '_ChannelPartnerUserInfo':
        return _ChannelPartnerUserInfo(
            self._http.do_get(f'partners/api/v2/channel_partners/{cp_id}/'))

    def _patch_channel_partner_state(self, cp_id: UUID, state: str) -> None:
        response = self._http.do_patch(f'partners/api/v2/channel_partners/{cp_id}/', {'state': state})
        actual_state = response['state']
        if state != actual_state:
            raise RuntimeError(
                f'Unexpected target state {actual_state}; expected is {state}')

    def get_aggregated_usage_data(self, cp_id: UUID) -> '_UsageData':
        return _UsageData(
            self._http.do_get(f'partners/api/v2/channel_partners/{cp_id}/aggregate/'))

    def _change_partner_state(self, cp_id: UUID, state: str) -> None:
        data = {"targetState": state}
        response = self._http.do_post(
            f'partners/api/v2/channel_partners/{cp_id}/change_state/', data)
        confirmation_data = {
            "changeId": response["changeId"],
            "code": response['code'],
            }
        response = self._http.do_post(
            f'partners/api/v2/channel_partners/{cp_id}/confirm_state/', confirmation_data)
        actual_state = response['state']
        if state != actual_state:
            raise RuntimeError(f'Unexpected target state {actual_state}; expected is {state}')

    def shutdown_channel_partner(self, cp_id: UUID) -> None:
        self._change_partner_state(cp_id, _TargetState.SHUTDOWN)

    def suspend_channel_partner(self, partner_id: UUID) -> None:
        self._patch_channel_partner_state(partner_id, _TargetState.SUSPENDED)

    def get_channel_structure(self, partner_id: UUID) -> Collection['_ChannelPartnerUserInfo']:
        response = self._http.do_get(
            f'partners/api/v2/channel_partners/{partner_id}/channel_structure/')
        return [_ChannelPartnerUserInfo(p) for p in response]

    def get_self_channel_structure(self) -> Collection['_ChannelPartnerUserInfo']:
        response = self._http.do_get('partners/api/v2/channel_partners/channel_structure/')
        channel_partners = response['channelPartners']
        return [_ChannelPartnerUserInfo(p) for p in channel_partners]

    def list_external_ids(self, cp_id: UUID) -> Collection['_ChannelPartnerExternalId']:
        result = self._http.do_get(f'partners/api/v2/channel_partners/{cp_id}/external_ids/')
        return [_ChannelPartnerExternalId(external_id) for external_id in result]

    def set_external_id(self, external_id: str, target_channel_partner_id: UUID, cp_id: UUID) -> None:
        data = {
            "customId": external_id,
            "channelPartner": str(target_channel_partner_id),
            }
        self._http.do_post(
            f'partners/api/v2/channel_partners/{cp_id}/external_ids/', data)

    def get_external_id_details(
            self,
            external_id: str,
            cp_id: UUID,
            ) -> Optional['_ChannelPartnerExternalId']:
        try:
            return _ChannelPartnerExternalId(self._http.do_get(
                f'partners/api/v2/channel_partners/{cp_id}/external_ids/{external_id}/'))
        except _NotFound:
            return None

    def update_external_id_fully(
            self,
            old_external_id: str,
            cp_id: UUID,
            new_external_id: str,
            target_cp_id: UUID,
            ) -> None:
        data = {"customId": new_external_id, "channelPartner": str(target_cp_id)}
        self._http.do_put(
            f'partners/api/v2/channel_partners/{cp_id}/external_ids/{old_external_id}/', data)

    def patch_external_id_name(
            self,
            old_external_id: str,
            new_external_id: str,
            cp_id: UUID,
            ) -> None:
        data = {"customId": new_external_id}
        self._http.do_patch(
            f'partners/api/v2/channel_partners/{cp_id}/external_ids/{old_external_id}/', data)

    def delete_external_id(self, external_id: str, cp_id: UUID) -> None:
        self._http.do_delete(
            f'partners/api/v2/channel_partners/{cp_id}/external_ids/{external_id}/')

    def list_own_organizations(self) -> Collection[ChannelPartnerOrganizationData]:
        raw = self._get_paginated_result('partners/api/v2/organizations/')
        return [ChannelPartnerOrganizationData(raw_org) for raw_org in raw]

    def list_organizations_for_channel_partner(
            self,
            channel_partner_id: UUID,
            ) -> Collection[ChannelPartnerOrganizationData]:
        raw = self._get_paginated_result(
            f'partners/api/v2/channel_partners/{str(channel_partner_id)}/organizations/')
        return [ChannelPartnerOrganizationData(e) for e in raw]

    def get_organization(self, organization_id: UUID) -> ChannelPartnerOrganizationData:
        raw = self._http.do_get(
            f'partners/api/v2/organizations/{str(organization_id)}/')
        return ChannelPartnerOrganizationData(raw)

    def create_organization(
            self, name: str, channel_partner_id: UUID) -> ChannelPartnerOrganizationData:
        raw = self._http.do_post(
            'partners/api/v2/organizations/',
            {
                'name': name,
                'channelPartner': str(channel_partner_id),
                })
        return ChannelPartnerOrganizationData(raw)

    def set_organization_user_role(
            self, organization_id: UUID, user_email: str, role_id: str) -> None:
        self._http.do_post(
            f'partners/api/v2/organizations/{str(organization_id)}/users/',
            {
                'email': user_email,
                'roleId': role_id,
                },
            )

    def update_organization_properties(
            self,
            organization_id: UUID,
            properties: Mapping[str, Any],
            ) -> ChannelPartnerOrganizationData:
        raw = self._http.do_patch(
            f'partners/api/v2/organizations/{str(organization_id)}/',
            properties,
            )
        return ChannelPartnerOrganizationData(raw)

    def set_channel_partner_access_level(
            self, organization_id: UUID, access_level_id: str | None) -> None:
        self.update_organization_properties(
            organization_id,
            {'channelPartnerAccessLevel': access_level_id},
            )

    def bind_cloud_system_to_organization(
            self,
            system_name: str,
            organization_id: UUID,
            customization_name: str,
            ) -> tuple[UUID, str]:
        data = {
            "name": system_name,
            "customization": customization_name,
            "organization": str(organization_id),
            }
        try:
            response = self._http.do_post('partners/api/v2/cloud_systems/', data)
        except _InternalServerError:
            raise CannotBindSystemToOrganization()
        return response['id'], response['authKey']

    def _patch_system(self, system_id: UUID, data: Mapping[str, Any]) -> None:
        self._http.do_patch(f'partners/api/v2/cloud_systems/{str(system_id)}/', data)

    def suspend_channel_partner_for_system(self, system_id: UUID) -> None:
        self._patch_system(system_id, {"state": _TargetState.SUSPENDED})

    def add_group_for_system(self, system_id: UUID, group_id: UUID) -> None:
        self._patch_system(system_id, {"groupId": str(group_id)})

    def get_system(self, system_id: UUID) -> '_CloudSystem':
        return _CloudSystem(self._http.do_get(f'partners/api/v2/cloud_systems/{str(system_id)}/'))

    def delete_system(self, system_id: UUID) -> None:
        self._http.do_delete(f'partners/api/v2/cloud_systems/{str(system_id)}/')

    def wait_for_active_system(self, system_id: UUID) -> None:
        started_at = time.monotonic()
        timeout = 5
        while True:
            if self.get_system(system_id).system_is_active():
                return
            if time.monotonic() - started_at > timeout:
                raise RuntimeError(f"System is not active within {timeout} seconds")
            _logger.debug("System is not active yet, waiting...")
            time.sleep(0.5)

    def list_systems_in_organization(self, organization_id: UUID) -> Collection['_CloudSystem']:
        response = self._http.do_get(
            f'partners/api/v2/organizations/{organization_id}/cloud_systems/')
        return [_CloudSystem(system) for system in response['results']]

    def list_systems_in_organization_for_user(
            self, organization_id: UUID) -> Collection['_CloudSystem']:
        response = self._http.do_get(
            f'partners/api/v2/organizations/{organization_id}/cloud_systems/user_systems/')
        return [_CloudSystem(system) for system in response['results']]

    def add_user_to_organization(
            self,
            organization_id: UUID,
            user_email: str,
            role_id: str,
            ):
        data = {
            'email': user_email,
            'roleId': role_id,
            }
        raw = self._http.do_post(
            f'partners/api/v2/organizations/{organization_id}/users/',
            data,
            )
        return OrganizationUser(raw)

    def create_group(
            self,
            group_name: str,
            organization_id: UUID,
            parent_group_id: Optional[UUID] = None,
            ) -> UUID:
        parent_group_id_str = "" if parent_group_id is None else str(parent_group_id)
        data = {
            "name": group_name,
            "parentId": parent_group_id_str,
            "organizationId": str(organization_id),
            }
        return UUID(self._http.do_post('partners/api/v2/groups/', data)['id'])


class ChannelPartnerRole:

    def __init__(self, raw_data: _HttpContent):
        self._raw_data = raw_data

    def get_id(self) -> UUID:
        return UUID(self._raw_data['id'])

    def get_name(self) -> str:
        return self._raw_data['name']

    def list_permissions(self) -> Collection[str]:
        return self._raw_data['permissions']


class _CloudSystem:

    def __init__(self, raw_data: _HttpContent):
        self._raw_data = raw_data

    def get_id(self) -> UUID:
        return UUID(self._raw_data['id'])

    def get_name(self) -> str:
        return self._raw_data['name']

    def _get_state(self) -> Collection[str]:
        return self._raw_data['system_state']

    def channel_partner_is_suspended(self) -> bool:
        state = self._raw_data['state']
        if state == _TargetState.SUSPENDED:
            return True
        elif state in [_TargetState.SHUTDOWN, _TargetState.ACTIVE]:
            return False
        else:
            raise RuntimeError(f"Unexpected state {state!r}")

    def get_organization_id(self) -> UUID:
        return UUID(self._raw_data['organization'])

    def system_is_active(self) -> bool:
        actual_status = self._get_state()
        if actual_status == _TargetSystemState.ACTIVE:
            return True
        elif actual_status == _TargetSystemState.NOT_ACTIVE:
            return False
        else:
            raise RuntimeError(f'Unexpected status: {actual_status}')

    def get_group_id(self) -> Optional[UUID]:
        group_id = self._raw_data.get('groupId')
        if group_id is None:
            return None
        else:
            return UUID(group_id)


class _UsageData:

    def __init__(self, raw_data: _HttpContent):
        self._raw_data = raw_data

    def get_channel_partners_count(self) -> int:
        return self._raw_data['channelPartners']


DefaultChannelPartnerRoles = {
    'admin': ChannelPartnerRole(
        {
            'name': 'Administrator',
            'id': '00000000-0000-4000-8000-000000000001',
            'permissions': [
                'add_remove_organizations',
                'add_remove_service_quantities',
                'add_remove_sub_channel_partners',
                'administer_organization_systems',
                'alter_state_organizations',
                'alter_state_sub_channel_partners',
                'configure_channel_partner',
                'field_access_cp_admin',
                'manage_users',
                'view_service_reports',
                ],
            }),
    'manager': ChannelPartnerRole(
        {
            'name': 'Manager',
            'id': '00000000-0000-4000-8000-000000000002',
            'permissions': [
                'add_remove_organizations',
                'add_remove_service_quantities',
                'administer_organization_systems',
                'alter_state_organizations',
                'field_access_cp_manager',
                'view_service_reports',
                ],
            }),
    'reports_viewer': ChannelPartnerRole(
        {
            'name': 'Reports Viewer',
            'id': '00000000-0000-4000-8000-000000000003',
            'permissions': ['field_access_cp_accountant', 'view_service_reports'],
            }),
    }


class _ChannelPartnerUserInfo:

    def __init__(self, raw_data: _HttpContent):
        self._raw_data = raw_data

    def get_email(self) -> str:
        return self._raw_data.get('email')

    def get_name(self) -> str:
        return self._raw_data.get('name')

    def get_id(self) -> Optional[UUID]:
        id_value = self._raw_data.get('id')
        if id_value is None:
            return None
        return UUID(id_value)

    def get_title(self) -> str:
        return self._raw_data.get('title')

    def list_roles(self) -> Collection[str]:
        default_roles = self._raw_data.get('roles')
        if default_roles is not None:
            return default_roles
        return self._raw_data.get('ownRoles')

    def list_role_ids(self) -> Collection[UUID]:
        default_roles = self._raw_data.get('rolesIds')
        if default_roles is not None:
            role_ids = default_roles
        else:
            role_ids = self._raw_data.get('ownRolesIds', [])
        return [UUID(role_id) for role_id in role_ids]

    def list_attributes(self) -> Mapping[str, str]:
        return self._raw_data.get('attributes')

    def get_state(self) -> str:
        main_state = self._raw_data.get('state')
        if main_state is not None:
            return main_state
        return self._raw_data.get('effectiveState')

    def is_active(self) -> bool:
        return self.get_state() == _TargetState.ACTIVE

    def is_suspended(self) -> bool:
        return self.get_state() == _TargetState.SUSPENDED

    def is_shutdown(self) -> bool:
        return self.get_state() == _TargetState.SHUTDOWN

    def list_subpartners(self) -> Collection['_ChannelPartnerUserInfo']:
        return [_ChannelPartnerUserInfo(p) for p in self._raw_data.get('subChannels', [])]


class _TargetState:
    ACTIVE = 'active'
    SUSPENDED = 'suspended'
    SHUTDOWN = 'shutdown'


class _TargetSystemState:
    ACTIVE = 'activated'
    NOT_ACTIVE = 'notActivated'


class _ChannelPartnerExternalId:

    def __init__(self, raw_data: _HttpContent):
        self._raw_data = raw_data

    def get_custom_id(self) -> str:
        return self._raw_data['customId']

    def get_channel_partner_uuid(self) -> UUID:
        return UUID(self._raw_data['channelPartner'])

    def get_full_id(self) -> str:
        return self._raw_data['fullId']


class CloudAccountFactory:

    def __init__(
            self,
            cloud_host: str,
            autotest_email: str,
            autotest_email_password: str,
            cert_path: Path,
            ):
        self._cloud_host = cloud_host
        self._autotest_email = autotest_email
        self._autotest_email_password = autotest_email_password
        self._cert_path = cert_path

    def create_account(self) -> CloudAccount:
        unique_id = int(time.perf_counter_ns())
        # To be able to get the activation code via API,
        # the email must contain specific substring.
        [name, domain] = self._autotest_email.split('@')
        email = f'{name}+noptixautoqa+{unique_id}+sendemail@{domain}'  # noqa SpellCheckingInspection
        cloud_account = CloudAccount(
            self._cloud_host,
            email,
            cert_path=self._cert_path,
            )
        cloud_account.register_user()
        try:
            code = cloud_account.get_activation_code()
        except Forbidden:
            _logger.debug(
                "Failed to get activation code: forbidden. Trying as the privileged user ...")
            headers = cloud_account.get_privileged_auth_headers()
            code = cloud_account.get_activation_code(headers)
        cloud_account.activate_user(code)
        return cloud_account

    def create_unregistered_account(self) -> CloudAccount:
        account_idx = int(time.perf_counter_ns())
        [name, domain] = self._autotest_email.split('@')
        email = f'{name}+noptixautoqa-{account_idx}+sendemail@{domain}'
        cloud_account = CloudAccount(
            self._cloud_host,
            email,
            cert_path=self._cert_path,
            )
        return cloud_account

    @lru_cache()
    def grant_channel_partner_access(self) -> Sequence[_HttpContent]:
        with self.temp_account() as cloud_account:
            cloud_account_cp_api = cloud_account.make_channel_partner_api()
            return cloud_account_cp_api.grant_channel_partner_access(cloud_account.user_email)

    def prepare_root_cp_with_admin(
            self, cp_data: Sequence[_HttpContent]) -> tuple[UUID, CloudAccount]:
        raw_users = cp_data[0]['users']
        for entry in raw_users:
            email = entry['email']
            if 'defaultadmin' in email:
                root_admin_account = self._prepare_account(email)
                return UUID(entry['channelPartnerId']), root_admin_account
        raise RuntimeError(f"Root CP and its admin were not found among {raw_users}")

    def prepare_sub_cp_with_admin(
            self, cp_data: Sequence[_HttpContent]) -> tuple[UUID, CloudAccount]:
        raw_users = cp_data[0]['users']
        for entry in raw_users:
            email = entry['email']
            if 'defaultcpadmin' in email:
                root_admin_account = self._prepare_account(email)
                return UUID(entry['channelPartnerId']), root_admin_account
        raise RuntimeError(f"Sub CP and its admin were not found among {raw_users}")

    def prepare_cp_organization_with_admin(
            self, cp_data: Sequence[_HttpContent]) -> tuple[UUID, CloudAccount]:
        raw_users = cp_data[0]['users']
        for entry in raw_users:
            if 'organizationId' in entry.keys():
                organization_admin_account = self._prepare_account(entry['email'])
                return UUID(entry['organizationId']), organization_admin_account
        raise RuntimeError(
            f"Channel Partner organization and its admin were not found among {raw_users}")

    @contextmanager
    def temp_account(self) -> AbstractContextManager[CloudAccount]:
        account = self.create_account()
        try:
            yield account
        finally:
            self._prune_account(account)

    @contextmanager
    def unregistered_temp_account(self) -> AbstractContextManager[CloudAccount]:
        account = self.create_unregistered_account()
        try:
            yield account
        finally:
            self._prune_account(account)

    @staticmethod
    def _prune_account(account: CloudAccount) -> None:
        if account.user_is_accessible():
            _logger.debug("Disconnect account %s's test systems", account.user_email)
            for system_id in account.list_system_ids():
                _logger.debug("Disconnect system %s", system_id)
                try:
                    account.disconnect_system(system_id)
                except Exception as e:
                    _logger.warning("Failed to disconnect system %s: %s", system_id, e)
            _logger.debug("Remove account %s", account.user_email)
            account_info = account.get_self_info()
            if account_info.account_2fa_is_enabled():
                account.disable_2fa()
            account.delete()
        else:
            _logger.debug(
                "Account %s not found. It may be deleted or not registered at all.",
                account.user_email)

    def _prepare_account(self, email: str) -> CloudAccount:
        account = CloudAccount(
            self._cloud_host,
            email,
            cert_path=self._cert_path,
            )
        account.register_user()
        try:
            code = account.get_activation_code()
        except Forbidden:
            _logger.debug(
                "Failed to get activation code: forbidden. Trying as the privileged user ...")
            headers = account.get_privileged_auth_headers()
            code = account.get_activation_code(headers)
        account.activate_user(code)
        return account

    def get_imap_credentials(self) -> tuple[str, str]:
        return self._autotest_email, self._autotest_email_password


class CloudInaccessible(Exception):
    pass


class BatchRequestFailed(Exception):
    pass


class CannotBindSystemToOrganization(Exception):
    pass
