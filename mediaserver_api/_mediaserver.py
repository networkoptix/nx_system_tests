# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from __future__ import annotations

import functools
import hashlib
import ipaddress
import json
import logging
import os
import time
import urllib.parse
from abc import ABCMeta
from abc import abstractmethod
from collections import defaultdict
from collections.abc import ByteString
from collections.abc import Collection
from collections.abc import Generator
from collections.abc import Iterable
from collections.abc import Mapping
from collections.abc import Sequence
from contextlib import contextmanager
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from http import HTTPStatus
from pprint import pformat
from typing import Any
from typing import Literal
from typing import NamedTuple
from typing import Optional
from typing import Type
from typing import Union
from urllib.parse import urlparse
from uuid import UUID
from uuid import uuid1
from uuid import uuid3
from uuid import uuid4

import websocket

from distrib import SpecificFeatures
from distrib import Version
from mediaserver_api._audit_trail import AuditTrail
from mediaserver_api._base_resource import BaseResource
from mediaserver_api._bookmarks import _BaseBookmark
from mediaserver_api._cameras import BaseCamera
from mediaserver_api._cameras import CameraStatus
from mediaserver_api._cameras import MotionType
from mediaserver_api._cameras import RecordingType
from mediaserver_api._events import EventCondition
from mediaserver_api._events import EventQueue
from mediaserver_api._events import EventState
from mediaserver_api._events import Rule
from mediaserver_api._events import RuleAction
from mediaserver_api._http import AuthHandler
from mediaserver_api._http import DEFAULT_HTTP_TIMEOUT
from mediaserver_api._http import HttpBasicAuthHandler
from mediaserver_api._http import HttpBearerAuthHandler
from mediaserver_api._http import HttpConnectionError
from mediaserver_api._http import HttpDigestAuthHandler
from mediaserver_api._http import HttpReadTimeout
from mediaserver_api._http import NoAuthHandler
from mediaserver_api._http import http_request
from mediaserver_api._http_auth import key as http_auth_key
from mediaserver_api._http_exceptions import BadRequest
from mediaserver_api._http_exceptions import Forbidden
from mediaserver_api._http_exceptions import MediaserverApiConnectionError
from mediaserver_api._http_exceptions import MediaserverApiHttpError
from mediaserver_api._http_exceptions import MediaserverApiReadTimeout
from mediaserver_api._http_exceptions import NoContent
from mediaserver_api._http_exceptions import NonJsonResponse
from mediaserver_api._http_exceptions import NotFound
from mediaserver_api._http_exceptions import OldSessionToken
from mediaserver_api._http_exceptions import Unauthorized
from mediaserver_api._ldap_settings import LdapSearchBase
from mediaserver_api._ldap_settings import _LdapSettings
from mediaserver_api._ldap_settings import _LdapSettingsV0
from mediaserver_api._merge_exceptions import ExplicitMergeError
from mediaserver_api._metrics import Alarm
from mediaserver_api._metrics import MetricsValues
from mediaserver_api._middleware import check_response_for_credentials
from mediaserver_api._storage import Storage
from mediaserver_api._storage import StorageUnavailable
from mediaserver_api._storage import _StorageType
from mediaserver_api._testcamera_data import Testcamera
from mediaserver_api._testcamera_data import testcamera_raw_input
from mediaserver_api._time_period import TimePeriod
from mediaserver_api._users import BaseUser
from mediaserver_api._users import Permissions
from mediaserver_api._users import SYSTEM_ADMIN_USER_ID
from mediaserver_api._web_pages import WebPage
from mediaserver_api.analytics import AnalyticsEngine
from mediaserver_api.analytics import AnalyticsEngineCollection
from mediaserver_api.analytics import AnalyticsEngineSettings
from mediaserver_api.analytics import AnalyticsTrack

_logger = logging.getLogger(__name__)

_DEFAULT_API_USER = 'admin'
_INITIAL_API_PASSWORD = 'admin'


def _format_uuid(resource_id: Union[str, UUID], strict: bool = False) -> str:
    if strict and not isinstance(resource_id, UUID):
        raise TypeError(f"{resource_id} must be uuid.UUID type, not {resource_id.__class__}")
    if isinstance(resource_id, str):
        UUID(resource_id)  # Check it's a UUID, don't force format.
        return resource_id
    if isinstance(resource_id, UUID):
        return str(resource_id)
    raise TypeError("{} should be str or uuid.UUID type".format(resource_id))


class LicenseAddError(Exception):

    def __init__(self, error_id, message):
        super().__init__(f"Error {error_id}: {message}")
        self.error_id = error_id
        self.message = message


class NotAttachedToCloud(Exception):
    pass


class TooManyAttempts(Exception):

    def __init__(self, url):
        super().__init__(f"Too many URL hits for {url} in a short period of time")


def _retry_on_too_many_attempts(func):
    @functools.wraps(func)
    def decorated(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except TooManyAttempts as e:
            _logger.warning(f"{e}. Waiting a second before one more try")
            time.sleep(1)
        return func(*args, **kwargs)

    return decorated


class StatisticsReport(NamedTuple):
    id: UUID
    system_id: UUID
    parent_id: UUID
    plugin_info: list[Mapping[str, Any]]
    hdd_list: list[str]
    physical_memory: int
    product_name: str
    public_ip: str
    publication_type: str
    cpu_architecture: str
    cpu_model: str
    flags: set
    full_version: str
    max_cameras: int
    status: str
    system_runtime: str
    version: str
    backup_start: int
    backup_type: str
    backup_days_of_week: str
    backup_duration: int
    backup_bitrate: int
    backup_bitrate_bps: list[Mapping[str, Any]]


class MotionParameters(NamedTuple):
    motion_mask: str
    record_before_motion_sec: int
    record_after_motion_sec: int


def _get_manifest_group(manifest, path):
    group = manifest  # Root group.
    for name in path:
        for subgroup in group['groups']:
            if subgroup['name'] == name:
                group = subgroup
                break
        else:
            raise RuntimeError(f"Cannot find {path} group in manifest")
    return group


def _get_manifest_param_id(group, name):
    for param in group['params']:
        if param['name'] == name:
            return param['id']
    raise RuntimeError(f"Cannot find {name} param in {group['name']} group")


class Credentials(NamedTuple):
    username: str
    password: str
    auth_type: str
    token: Optional[str]


class _CreatedUser(NamedTuple):
    id: UUID
    name: str
    password: str


class _EmailSettings(NamedTuple):
    connection_type: Optional[str]
    email: Optional[str]
    password: Optional[str]
    server: Optional[str]
    signature: Optional[str]
    support_address: Optional[str]
    user: Optional[str]


class _IncompleteLicenseBlock(Exception):
    pass


class _License(BaseResource):

    def __init__(self, raw_data):
        # Create a synthetic ID to match the interface.
        license_id = uuid3(UUID(int=0), raw_data['key'])
        super().__init__(raw_data, resource_id=license_id)
        self.license_block = self._license_block(raw_data)
        try:
            self.deactivations = int(self.license_block['DEACTIVATIONS'])
            self.hwid = self.license_block['HWID']
        except KeyError as e:
            raise _IncompleteLicenseBlock("%s is missing", e)
        self.key = raw_data['key']

    @classmethod
    def _list_compared_attributes(cls):
        return ['deactivations', 'hwid', 'key']

    @staticmethod
    def _license_block(raw_data):
        license_block = {}
        for pair in raw_data['licenseBlock'].splitlines():
            key, value = pair.split('=', 1)
            license_block[key] = value
        return license_block


class Videowall(BaseResource):

    def __init__(self, raw_data):
        super().__init__(raw_data, resource_id=UUID(raw_data['id']))
        self._autorun = raw_data['autorun']
        self._items = raw_data['items']
        self._matrices = raw_data['matrices']
        self._name = raw_data['name']
        self._parent_id = UUID(raw_data['parentId'])
        self._screens = raw_data['screens']
        self._timeline = raw_data['timeline']
        self._type_id = UUID(raw_data['typeId'])

    @classmethod
    def _list_compared_attributes(cls):
        return [
            '_autorun',
            '_items',
            '_matrices',
            '_name',
            '_parent_id',
            '_screens',
            '_timeline',
            '_type_id',
            ]


class _Resources:

    def __init__(self, items: Sequence[BaseResource]):
        self._items = items

    def diff(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        result = {}
        self_items = {item.id: item for item in self._items}
        other_items = {item.id: item for item in other._items}
        for missing_id in self_items.keys() - other_items.keys():
            result[f'{missing_id}'] = {'action': 'removed', 'self': self_items[missing_id]}
        for same_id in self_items.keys() & other_items.keys():
            self_item = self_items[same_id]
            other_item = other_items[same_id]
            for key, value in self_item.diff(other_item).items():
                result[f'{same_id}/{key}'] = value
        for new_id in other_items.keys() - self_items.keys():
            result[f'{new_id}'] = {'action': 'added', 'other': other_items[new_id]}
        return result


class _FullInfo:

    def __init__(
            self,
            cameras,
            camera_history,
            layouts,
            licenses,
            rules,
            servers,
            storages,
            users,
            videowalls,
            ):
        self._cameras = _Resources(cameras)
        self._camera_history = _Resources(camera_history)
        self._layouts = _Resources(layouts)
        self._licenses = _Resources(licenses)
        self._rules = _Resources(rules)
        self._servers = _Resources(servers)
        self._storages = _Resources(storages)
        self._users = _Resources(users)
        self._videowalls = _Resources(videowalls)

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        return not self.diff(other)

    def diff(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        result = {}
        for key, value in self._cameras.diff(other._cameras).items():
            result[f'cameras/{key}'] = value
        for key, value in self._camera_history.diff(other._camera_history).items():
            result[f'camera_history/{key}'] = value
        for key, value in self._layouts.diff(other._layouts).items():
            result[f'layouts/{key}'] = value
        for key, value in self._licenses.diff(other._licenses).items():
            result[f'licenses/{key}'] = value
        for key, value in self._rules.diff(other._rules).items():
            result[f'rules/{key}'] = value
        for key, value in self._servers.diff(other._servers).items():
            result[f'servers/{key}'] = value
        for key, value in self._storages.diff(other._storages).items():
            result[f'storages/{key}'] = value
        for key, value in self._users.diff(other._users).items():
            result[f'users/{key}'] = value
        for key, value in self._videowalls.diff(other._videowalls).items():
            result[f'videowalls/{key}'] = value
        return result


def log_full_info_diff(log_fn, diff_list):
    for key, value in diff_list.items():
        log_fn('%s: %s', key, value)


class _CameraHistory(BaseResource):

    def __init__(self, raw_data):
        super().__init__(raw_data, resource_id=UUID(raw_data['serverGuid']))
        self._archived_cameras = [UUID(camera_id) for camera_id in raw_data['archivedCameras']]

    @classmethod
    def _list_compared_attributes(cls):
        return ['_archived_cameras']


class MediaserverApi(metaclass=ABCMeta):
    """Mediaserver API wrapper. Same interface for all API versions.

    Wraps API responses with objects with easy and typing-aware data access.
    """

    _basic_and_digest_auth_required = False
    _preferred_auth_type: str
    _version: str
    _site_term: str
    audit_trail_events: NamedTuple

    def __init__(
            self,
            base_url: str,
            ca_cert: Optional[str, os.PathLike] = None,
            auth_type: Optional[str] = None,
            ):
        """Base class for Mediaserver API wrappers of all versions.

        :param base_url: Base URL; port defaults to 7001; path and query ignored.
        :param ca_cert: Optional path to CA certificate to trust. If provided, default scheme is
            HTTPS. (HTTP otherwise.)
        """
        parsed = urlparse(base_url)
        self._scheme = 'https'
        if parsed.port is not None:
            self._netloc = parsed.netloc
        else:
            self._netloc = parsed.netloc + ':7001'
        if ca_cert is not None:
            _logger.info("Trust CA cert passed via param: %s", ca_cert)
            self._ca_cert = ca_cert
        elif 'FT_CA_BUNDLE' in os.environ:
            cert = os.environ['FT_CA_BUNDLE']
            _logger.info("Trust CA cert passed via env var: %s", cert)
            self._ca_cert = cert
        else:
            _logger.info("Trust CA certs from OS")
            self._ca_cert = None
        user = parsed.username or _DEFAULT_API_USER
        password = parsed.password or _INITIAL_API_PASSWORD
        if auth_type is None:
            auth_type = self._preferred_auth_type
        self._auth_handler = self._make_auth_handler(user, password, auth_type)

        # TODO: Split this class into composing parts: `SystemApi`, `CamerasApi`, etc.

    def __repr__(self):
        return '<{} at {}>'.format(self.__class__.__name__, self.http_url(''))

    @functools.lru_cache()
    def specific_features(self):
        raw = self._http_download('/static/specific_features.txt')
        return SpecificFeatures(raw)

    def _make_auth_handler(self, username: str, password: str, auth_type: str) -> AuthHandler:
        if auth_type == 'bearer':
            return HttpBearerAuthHandler(username, password, self._make_token_provider())
        if auth_type == 'digest':
            return HttpDigestAuthHandler(username, password)
        if auth_type == 'basic':
            return HttpBasicAuthHandler(username, password)
        if auth_type == 'no_auth':
            return NoAuthHandler()
        raise RuntimeError(f"Unsupported auth type: {auth_type}")

    def _make_token_provider(self):
        return self.__class__(
            self.http_url('', with_credentials=False),
            self._ca_cert,
            auth_type='no_auth',
            )

    def import_auth(self, other: MediaserverApi):
        self._auth_handler.subsume_from_master(other.get_auth_handler())

    def get_auth_handler(self) -> AuthHandler:
        return self._auth_handler

    def enable_auth_refresh(self):
        if not isinstance(self._auth_handler, HttpBearerAuthHandler):
            raise RuntimeError("Bearer authentication only requires refresh")
        self._auth_handler.enable_refresh_old_token()

    def disable_auth_refresh(self):
        if not isinstance(self._auth_handler, HttpBearerAuthHandler):
            raise RuntimeError("Bearer authentication only requires refresh")
        self._auth_handler.disable_refresh_old_token()

    def make_auth_header(self) -> str:
        if isinstance(self._auth_handler, HttpDigestAuthHandler):
            # Digest requires info about request in order to make correct auth header.
            # Basic is used instead.
            basic_auth_handler = self._make_auth_handler(
                self._user, self._password, auth_type='basic')
            return basic_auth_handler.make_authorization_header()
        return self._auth_handler.make_authorization_header()

    def set_password(self, password):
        self.set_credentials(self._user, password)

    def set_credentials(self, username, password):
        self._auth_handler = self._auth_handler.with_credentials(username, password)

    def reset_credentials(self):
        self._auth_handler = self._make_auth_handler(
            _DEFAULT_API_USER,
            _INITIAL_API_PASSWORD,
            auth_type=self._preferred_auth_type,
            )

    def use_local_auth(self):
        self._auth_handler = self._make_auth_handler(
            self._user,
            self._password,
            auth_type=self.auth_type,
            )

    @property
    def _user(self) -> str:
        return self._auth_handler.username

    @property
    def _password(self) -> str:
        return self._auth_handler.password

    @property
    def auth_type(self) -> str:
        if isinstance(self._auth_handler, HttpBearerAuthHandler):
            return 'bearer'
        if isinstance(self._auth_handler, HttpDigestAuthHandler):
            return 'digest'
        if isinstance(self._auth_handler, HttpBasicAuthHandler):
            return 'basic'
        if isinstance(self._auth_handler, NoAuthHandler):
            return 'no_auth'
        raise RuntimeError("Unknown auth type")

    def _userinfo(self):
        return ':'.join((
            MediaserverApi._quote_userinfo_part(self._user),
            MediaserverApi._quote_userinfo_part(self._password),
            ))

    @staticmethod
    def _quote_userinfo_part(s):
        """Encode username and password correctly.

        See: RFC 3986
        See: https://serverfault.com/a/1001324/208965
        userinfo    = *( unreserved / pct-encoded / sub-delims / ":" )
        unreserved  = ALPHA / DIGIT / "-" / "." / "_" / "~"
        pct-encoded = "%" HEXDIG HEXDIG
        sub-delims  = "!" / "$" / "&" / "'" / "(" / ")"

        I.e., sub-delims are allowed and may not be quoted.
        """
        return urllib.parse.quote(s, safe="!$&'()*+,;=")

    def http_url(self, path, with_credentials=False):
        path = path.lstrip('/')
        if with_credentials:
            return f'{self._scheme}://{self._userinfo()}@{self._netloc}/{path}'
        else:
            return f'{self._scheme}://{self._netloc}/{path}'

    def url_with_another_host_and_port(self, host, port):
        return f'{self._scheme}://{self._userinfo()}@{host}:{port}/'

    def secure_url(self, path):
        path = path.lstrip('/')
        return f'https://{self._netloc}/{path}'

    def media_url(self, path):
        path = path.lstrip('/')
        return f'rtsp://{self._userinfo()}@{self._netloc}/{path}'

    def rct_media_url(self, camera_id, profile='primary', no_cached_gop=False):
        # TODO: Sort out URL methods.
        url = self.media_url(str(camera_id))
        url += '?stream=' + {'primary': '0', 'secondary': '1'}[profile]
        if no_cached_gop:
            url += '&disable_fast_channel_zapping'
        return url

    def open_websocket(self, path: str, timeout_sec=10):
        if self._ca_cert is not None:
            url = self._secure_websocket_url(path)
            ssl_options = dict(ca_certs=self._ca_cert)
        else:
            url = self._websocket_url(path)
            ssl_options = None
        headers = dict(Authorization=self.make_auth_header())
        _logger.debug('Create websocket connection: %s', url)
        try:
            return websocket.create_connection(
                url,
                header=headers,
                timeout=timeout_sec,
                sslopt=ssl_options,
                )
        except websocket.WebSocketBadStatusException as exc:
            if exc.status_code == HTTPStatus.FORBIDDEN:
                raise WebSocketForbidden()
            raise

    def _websocket_url(self, path):
        path = path.lstrip('/')
        return f'ws://{self._netloc}/{path}'

    def _secure_websocket_url(self, path):
        # websocket with SSL, like HTTP/HTTPS.
        path = path.lstrip('/')
        return f'wss://{self._netloc}/{path}'

    def _request(self, method: str, path: str, params=None, timeout: float = DEFAULT_HTTP_TIMEOUT, **kwargs):
        if params:
            # Server, which uses QUrlQuery doesn't support spaces, encoded as "+".
            # See https://doc.qt.io/qt-5/qurlquery.html#handling-of-spaces-and-plus.
            params = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
            path = f'{path}?{params}'
        if 'json' in kwargs:
            content = kwargs['json']
        elif 'data' in kwargs:
            content = kwargs['data']
        else:
            content = None
        headers = kwargs.get('headers', {})
        started_at = time.perf_counter()
        url = self.http_url(path)
        response = http_request(
            method,
            url,
            content,
            headers=headers,
            timeout=timeout,
            auth_handler=self._auth_handler,
            ca_cert=self._ca_cert,
            )
        _logger.info(
            "HTTP API %(method)s %(url)s, "
            "took %(duration).3f sec, "
            "status %(status)s"
            "", {
                'method': method,
                'url': url,
                'path': path,
                'duration': time.perf_counter() - started_at,
                'status': response.status_code,
                })
        return response

    def http_get(self, path, params=None, timeout: float = DEFAULT_HTTP_TIMEOUT, **kwargs):
        params_str = pformat(params, indent=4)
        if '\n' in params_str or len(params_str) > 60:
            params_str = '\n' + params_str
        _logger.debug(
            'GET %s, timeout: %s sec, params: %s',
            self.http_url(path, with_credentials=True), timeout, params_str)
        assert 'data' not in kwargs
        assert 'json' not in kwargs
        return self._http_request('GET', path, params=params, timeout=timeout, **kwargs)

    def _make_json_request(self, method, path, data, timeout, **kwargs):
        data_str = json.dumps(data)
        if len(data_str) > 60:
            data_str = '\n' + json.dumps(data, indent=4)
        _logger.debug(
            '%s %s, timeout: %s sec, payload:\n%s',
            method, self.http_url(path, with_credentials=True), timeout, data_str)
        return self._http_request(method, path, json=data, timeout=timeout, **kwargs)

    def http_post(self, path, data, timeout: float = DEFAULT_HTTP_TIMEOUT, **kwargs):
        return self._make_json_request('POST', path, data, timeout, **kwargs)

    def http_patch(self, path, data, **kwargs):
        return self._make_json_request('PATCH', path, data, timeout=DEFAULT_HTTP_TIMEOUT, **kwargs)

    def http_put(self, path, data, **kwargs):
        return self._make_json_request('PUT', path, data, timeout=DEFAULT_HTTP_TIMEOUT, **kwargs)

    def http_delete(self, path, **kwargs):
        return self._http_request('DELETE', path, **kwargs)

    def _raise_for_status(self, response, response_json):
        if isinstance(response_json, dict):
            vms_error_dict = response_json
        else:
            vms_error_dict = {}
        vms_error_code = int(vms_error_dict.get('error', 0))
        vms_error_string = vms_error_dict.get('errorString', '')
        if vms_error_code:
            _logger.warning(
                "Mediaserver API responded with an error. "
                "Status code: %d. "
                "Error: %r",
                response.status_code,
                vms_error_dict)
        if response.status_code == 400:
            raise BadRequest(self._netloc, response, vms_error_dict)
        auth_result = response.headers.get('x-auth-result', '')
        if response.status_code == 401:
            raise Unauthorized(self._netloc, response, vms_error_dict)
        # Old API returns either 3 or 4 for requests failed due to insufficient user rights.
        # In tests there are no endpoints that returns vms error 3 and HTTP 200 OK on Forbidden
        # request. New API must return error code 4.
        if response.status_code == 403 or vms_error_code == 4:
            if auth_result == 'Auth_WrongSessionToken':
                raise OldSessionToken(self._netloc, response, vms_error_dict)
            raise Forbidden(self._netloc, response, vms_error_dict)
        if response.status_code == 404 or vms_error_code == 9:
            raise NotFound(self._netloc, response, vms_error_dict)
        # New API returns 422 status code instead of 401 if invalid credentials were passed.
        if response.status_code == 422:
            if 'Wrong password' in vms_error_string:
                raise Unauthorized(self._netloc, response, vms_error_dict)
            else:
                # New API returns 422 status in case when some parameter has an inappropriate value or missed
                raise BadRequest(self._netloc, response, vms_error_dict)
        if 400 <= response.status_code < 600 or vms_error_code != 0:
            raise MediaserverApiHttpError(self._netloc, response, vms_error_dict)

    def _retrieve_data(self, response, response_json):
        if not response.content:
            _logger.warning("Empty response.")
            return None
        if response_json is None:
            # VMS-12270: Server closes HTTP connection while sending data to client
            raise NonJsonResponse(self._netloc, response, {})
        if isinstance(response_json, dict) and 'reply' in response_json:
            return response_json['reply']
        return response_json

    @_retry_on_too_many_attempts
    def obtain_token(self, username: str, password: str):
        version = 'v1' if self._version == 'v0' else self._version
        url = f'rest/{version}/login/sessions'
        try:
            response = self._http_request('POST', url, data={
                'username': username,
                'password': password,
                })
        except Forbidden as e:
            if "Too many attempts, try again later" in str(e):
                raise TooManyAttempts(url)
            raise
        return response['token']

    @staticmethod
    def must_be_subsumed():
        return False

    def _http_request(self, method, path, timeout=DEFAULT_HTTP_TIMEOUT, **kwargs):
        try:
            response = self._request(method, path, timeout=timeout, **kwargs)
        except HttpReadTimeout as e:
            raise MediaserverApiReadTimeout(self._netloc, '%r: %s %r: %s' % (self, method, path, e))
        except HttpConnectionError as e:
            raise MediaserverApiConnectionError(self._netloc, '%r: %s %r: %s' % (self, method, path, e))
        if len(response.content) > 1000:
            resp_logger = _logger.getChild('http_resp.large')
        else:
            resp_logger = _logger.getChild('http_resp.small')
        resp_logger.debug("%s %s: JSON response:\n%s", method, path, response.json)
        self._raise_for_status(response, response.json)
        if response.json is not None:
            check_response_for_credentials(response.json, path)
        return self._retrieve_data(response, response.json)

    def _http_download(self, path, params=None):
        response = self._request('GET', path, params=params)
        self._raise_for_status(response, response_json=None)
        if response.status_code == 204:
            raise NoContent(f"No content returned on {response.url}")
        _logger.debug(
            "Got response with binary data: Content-Type: %s, Content-Length: %s",
            response.headers['Content-Type'], response.headers['Content-Length'])
        return response.content

    def _http_upload(self, path: str, data: bytes):
        headers = {
            'Content-Length': str(len(data)),
            'Content-Type': 'application/octet-stream',
            }
        response = self._request('POST', path, headers=headers, data=data)
        self._raise_for_status(response, response_json=None)

    @staticmethod
    def _prepare_params(params):
        return {key: value for key, value in params.items() if value is not None}

    @staticmethod
    def _format_permissions(permissions):
        if isinstance(permissions, str):
            raise RuntimeError("Permissions must be iterable, but not a single string")
        if permissions is not None:
            return "|".join(permissions)

    @abstractmethod
    def _prepare_auth_params(self, name, password):
        pass

    def auth_key(self, method):
        path = ''
        response = self.http_get('api/getNonce')
        realm, nonce = response['realm'], response['nonce']
        return http_auth_key(
            method=method,
            path=path,
            realm=realm,
            nonce=nonce,
            user=self._user,
            password=self._password,
            )

    @staticmethod
    def _url_args_start_end(period: TimePeriod):
        result = {'pos': period.start_ms}
        if period.complete:
            result['endPos'] = period.end_ms
        return result

    def _make_export_url(
            self, camera_id: UUID, period: TimePeriod, path_str, profile: Optional = 'primary',
            resolution: Optional = None):
        camera_id_safe = urllib.parse.quote(_format_uuid(camera_id), safe='')
        args = self._url_args_start_end(period)
        args = {**args, 'stream': {'primary': '0', 'secondary': '1'}[profile]}
        if resolution is not None:
            args = {**args, 'resolution': resolution}
        args_encoded = urllib.parse.urlencode(args)
        path = path_str.format(camera_id_safe, args_encoded)
        url = self.http_url(path, with_credentials=True)
        return url

    _mpjpeg_path_str = 'media/{}.mpjpeg?{}'

    def mpjpeg_url(self, camera_id: UUID, period: TimePeriod, profile='primary', resolution=None):
        return self._make_export_url(
            camera_id, period, self._mpjpeg_path_str, profile=profile, resolution=resolution)

    def mpjpeg_live_url(self, camera_id: UUID):
        camera_id_safe = urllib.parse.quote(_format_uuid(camera_id), safe='')
        args_encoded = urllib.parse.urlencode({'stream': '0'})
        path = self._mpjpeg_path_str.format(camera_id_safe, args_encoded)
        return self.http_url(path)

    def mp4_url(self, camera_id: UUID, period: TimePeriod, profile='primary'):
        return self._make_export_url(camera_id, period, 'media/{}.mp4?{}', profile=profile)

    def mkv_url(self, camera_id: UUID, period: TimePeriod, profile='primary'):
        return self._make_export_url(camera_id, period, 'media/{}.mkv?{}', profile=profile)

    def webm_url(self, camera_id: UUID, period: TimePeriod, profile='primary', resolution=None):
        return self._make_export_url(camera_id, period, 'media/{}.webm?{}', profile, resolution)

    def hls_url(self, camera_id: UUID, period: TimePeriod):
        return self._make_export_url(camera_id, period, 'hls/{}.m3u?{}')

    def direct_hls_url(self, camera_id: UUID, period: TimePeriod):
        return self._make_export_url(camera_id, period, 'hls/{}.mkv?{}')

    def direct_download(self, camera_id: UUID, period: TimePeriod) -> bytes:
        camera_id_safe = urllib.parse.quote(_format_uuid(camera_id), safe='')
        params = {'pos': period.start_ms, 'duration': int(period.duration_sec)}
        args_encoded = urllib.parse.urlencode(params)
        path = f'hls/{camera_id_safe}.mkv?{args_encoded}'
        url = self.http_url(path, with_credentials=False)
        response = http_request('GET', url, auth_handler=self._auth_handler, ca_cert=self._ca_cert)
        if response.content is None:
            raise RuntimeError(
                "Something went terribly wrong. "
                "Content MUST NOT be None in the Direct Download method")
        return response.content

    def rtsp_url(
            self,
            camera_id: UUID,
            period: Optional[TimePeriod] = None,
            stream='primary',
            codec=None,
            ):
        assert stream in ('primary', 'secondary')
        path = urllib.parse.quote(_format_uuid(camera_id), safe='')
        stream_args = self._prepare_params({
            'stream': 0 if stream == 'primary' else 1,
            'codec': codec,
            **(self._url_args_start_end(period) if period is not None else {}),
            })
        args_encoded = urllib.parse.urlencode(stream_args)
        path += f'?{args_encoded}'
        return self.media_url(path)

    def secure_rtsp_url(self, camera_id: UUID, period: Optional[TimePeriod] = None):
        path = urllib.parse.quote(_format_uuid(camera_id), safe='')
        args_encoded = urllib.parse.urlencode({
            'stream': '0',
            **(self._url_args_start_end(period) if period is not None else {}),
            })
        path += f'?{args_encoded}'
        path = path.lstrip('/')
        return f'rtsps://{self._userinfo()}@{self._netloc}/{path}'

    @abstractmethod
    def _add_user(self, primary):
        pass

    @abstractmethod
    def _modify_user(self, user_id, primary):
        pass

    def add_local_user(
            self,
            name: str,
            password: str,
            permissions: Optional[Iterable[str]] = None,
            group_id: Optional[Union[str, UUID]] = None,
            ) -> _CreatedUser:
        primary = self._make_local_user_primary_params(
            name,
            permissions=permissions,
            group_id=group_id,
            )
        auth_params = self._prepare_auth_params(name, password)
        user_id = self._add_user({**primary, **auth_params})
        return _CreatedUser(user_id, name, password)

    def add_local_admin(self, username, password):
        return self.add_local_user(username, password, [Permissions.ADMIN])

    def add_local_advanced_viewer(self, username, password):
        return self.add_local_user(username, password, Permissions.ADVANCED_VIEWER_PRESET)

    def add_local_viewer(self, username, password):
        return self.add_local_user(username, password, Permissions.VIEWER_PRESET)

    def add_local_live_viewer(self, username, password):
        return self.add_local_user(username, password, [Permissions.ACCESS_ALL_MEDIA])

    def _make_local_user_primary_params(
            self,
            name: str,
            permissions: Optional[Iterable[str]] = None,
            group_id: Optional[Union[str, UUID]] = None,
            ):
        return self._prepare_params({
            'name': name,
            'permissions': self._format_permissions(permissions),
            'userRoleId': _format_uuid(group_id) if group_id is not None else None,
            })

    def add_cloud_user(
            self,
            name: str,
            email: str,
            permissions: Optional[Iterable[str]] = None,
            group_id: Optional[Union[str, UUID]] = None,
            ):
        primary = self._make_cloud_user_primary_params(
            name,
            email,
            permissions=permissions,
            group_id=group_id,
            )
        return self._add_user(primary)

    def _make_cloud_user_primary_params(
            self,
            name: str,
            email: str,
            permissions: Optional[Iterable[str]] = None,
            group_id: Optional[Union[str, UUID]] = None,
            ):
        return self._prepare_params({
            'name': name,
            'email': email,
            'permissions': self._format_permissions(permissions),
            'userRoleId': _format_uuid(group_id) if group_id is not None else None,
            'isCloud': True,
            })

    def _add_ldap_user(
            self,
            name: str,
            permissions: Optional[Iterable[str]] = None,
            full_name: Optional[str] = None,
            email: Optional[str] = None,
            enable_basic_and_digest_auth: Optional[bool] = False,
            dn: Optional[str] = None,
            ):
        params = self._make_ldap_user_primary_params(
            name,
            permissions=permissions,
            full_name=full_name,
            email=email,
            enable_basic_and_digest_auth=enable_basic_and_digest_auth,
            dn=dn,
            )
        return self._add_user(params)

    def _make_ldap_user_primary_params(
            self,
            name: str,
            permissions: Optional[Iterable[str]] = None,
            full_name: Optional[str] = None,
            email: Optional[str] = None,
            enable_basic_and_digest_auth: Optional[bool] = False,
            dn: Optional[str] = None,
            ):
        if dn is not None:
            # Since VMS-37062 externalId is an object.
            if not self.server_older_than('vms_6.0'):
                dn = {
                    'dn': dn,
                    'synced': True,
                    }
        return self._prepare_params({
            'name': name,
            'permissions': self._format_permissions(permissions),
            'fullName': full_name,
            'email': email,
            'isHttpDigestEnabled': True if enable_basic_and_digest_auth else None,
            'externalId': dn,
            'isLdap': True,
            })

    def import_single_ldap_user(
            self,
            name: str,
            host: str,
            admin_dn: str,
            admin_password: str,
            search_base: Optional[LdapSearchBase] = None,
            enable_basic_and_digest_auth: bool = False,
            ):
        ldap_user_list = self.list_users_from_ldap_server(
            host=host,
            admin_dn=admin_dn,
            admin_password=admin_password,
            search_base=search_base,
            )
        try:
            [user] = [user for user in ldap_user_list if user['login'] == name]
        except ValueError:
            raise RuntimeError(
                f"No user {name} on LDAP server {host} with search base {search_base}")
        return self._add_ldap_user(
            name=user['login'],
            full_name=user['fullName'],
            email=user['email'],
            enable_basic_and_digest_auth=enable_basic_and_digest_auth,
            dn=user['dn'],
            )

    def add_generated_user(
            self,
            idx: int,
            parent_id: Optional[str] = None,
            group_id: Optional[str] = None,
            ):
        generated_user_id = UUID(f'58e20000-0000-0000-0000-{idx:012d}')
        name = f'User_{idx}'
        password = name
        email = f'{name}@gmail.com'
        primary = {
            'email': email,
            'id': str(generated_user_id),
            'isAdmin': False,
            'name': name,
            'password': password,
            'parentId': parent_id or '{00000000-0000-0000-0000-000000000000}',
            'permissions': Permissions.NO_GLOBAL,
            'typeId': '{774e6ecd-ffc6-ae88-0165-8f4a6d0eafa7}',  # noqa
            'url': '',
            'userRoleId': group_id or '{00000000-0000-0000-0000-000000000000}',
            }
        user_id = self._add_user(primary)
        assert user_id == generated_user_id
        return _CreatedUser(generated_user_id, name, password)

    def enable_user(self, user_id):
        self._modify_user(user_id, {'isEnabled': True})

    def disable_user(self, user_id):
        self._modify_user(user_id, {'isEnabled': False})

    def rename_user(self, user_id, new_name):
        self._modify_user(user_id, {'name': new_name})

    @abstractmethod
    def set_user_password(self, user_id, password):
        pass

    @abstractmethod
    def set_user_credentials(self, user_id, name, password):
        pass

    def set_user_email(self, user_id, email):
        self._modify_user(user_id, {'email': email})

    def set_user_permissions(self, user_id, permissions):
        self._modify_user(user_id, {'permissions': self._format_permissions(permissions)})

    def set_user_group(self, user_id, group_id):
        self._modify_user(user_id, {'userRoleId': _format_uuid(group_id)})

    @abstractmethod
    def remove_user(self, user_id):
        pass

    def get_current_user(self) -> BaseUser:
        for u in self.list_users():
            if u.name == self._user:
                return u
        raise AssertionError("Cannot find user that is currently logged in")

    @abstractmethod
    def list_users(self) -> Collection[BaseUser]:
        pass

    @abstractmethod
    def get_user(self, user_id):
        pass

    def _get_current_user_id(self) -> UUID:
        [current_user] = [u for u in self.list_users() if u.name == self._user]
        return current_user.id

    @abstractmethod
    def set_user_access_rights(self, user_id, resource_ids, access_type='view'):
        pass

    def revoke_access_rights(self, user_id):
        return self.set_user_access_rights(user_id=user_id, resource_ids=())

    def copy(self):
        return self.with_password(self._auth_handler.password)

    def with_password(self, password):
        return self.with_credentials(self._auth_handler.username, password)

    def with_credentials(self, username, password):
        return self.with_auth_handler(self._auth_handler.with_credentials(username, password))

    def with_basic_auth(self, username: str, password: str):
        return self.with_auth_handler(self._make_auth_handler(username, password, auth_type='basic'))

    def with_digest_auth(self, username: str, password: str):
        return self.with_auth_handler(self._make_auth_handler(username, password, auth_type='digest'))

    def with_local_bearer_auth(self, username: str, password: str):
        return self.with_auth_handler(self._make_auth_handler(username, password, auth_type='bearer'))

    def with_auth_handler(self, auth_handler):
        new_api = self.__class__(self.http_url(''), auth_type='no_auth')
        new_api._auth_handler = auth_handler
        return new_api

    def with_version(self, version_cls: Type[MediaserverApi]) -> MediaserverApi:
        api_with_version = version_cls(self.http_url(''), ca_cert=self._ca_cert)
        credentials = self.get_credentials()
        api_with_version.set_credentials(credentials.username, credentials.password)
        return api_with_version

    def as_user(self, user: _CreatedUser) -> MediaserverApi:
        api_for_user = self.__class__(self.http_url(''), ca_cert=self._ca_cert)
        api_for_user.set_credentials(user.name, user.password)
        return api_for_user

    def as_relay(
            self,
            relay_host: str,
            cloud_system_id: UUID,
            ca_cert: Optional[os.PathLike] = None,
            ) -> MediaserverApi:
        if ca_cert is None:
            ca_cert = self._ca_cert
        relay_api = self.__class__(self.http_url(''), ca_cert=ca_cert)
        relay_api._netloc = f'{cloud_system_id}.{relay_host}'
        relay_api._auth_handler = self._auth_handler
        # If the relay host points to a proxy service, the request is redirected
        # to the relay service closest to the VMS.
        response = relay_api._request('GET', path='')
        if response.status_code == 307:
            location_header = response.headers.get('location')
            redirect_url = urlparse(location_header)
            relay_api._netloc = redirect_url.netloc
        return relay_api

    @abstractmethod
    def _add_videowall(self, primary):
        pass

    def add_videowall(self, name):
        return self._add_videowall({'id': str(uuid4()), 'name': name})

    def add_generated_videowall(self, primary):
        return self._add_videowall(primary)

    @abstractmethod
    def remove_videowall(self, videowall_id):
        pass

    @abstractmethod
    def list_videowalls(self):
        pass

    def dummy_control_videowall(self, videowall_id):
        """Touch videowall. Do not alter the content of the videowall.

        Interaction between videowall and its elements is carried out using
        an internal binary protocol.
        """
        self.http_post('ec2/videowallControl', {'videowallGuid': _format_uuid(videowall_id)})

    def is_online(self):
        try:
            self.http_get('/api/ping')
        except MediaserverApiConnectionError:
            return False
        else:
            return True

    @abstractmethod
    def _request_with_required_authentication(self):
        pass

    def credentials_work(self):
        try:
            self._request_with_required_authentication()
        except Unauthorized:
            return False
        return True

    @abstractmethod
    def _get_server_info(self):
        pass

    class MediaserverInfo(metaclass=ABCMeta):

        def __init__(self, raw_data: Mapping[str, str]):
            self._raw_data = raw_data
            parsed = self._parse_raw_data()
            self.server_id = parsed['server_id']
            self.local_site_id = parsed['local_site_id']
            self.server_name: str = parsed['server_name']
            self.site_name: str = parsed['site_name']
            self.customization: str = parsed['customization']

        @abstractmethod
        def _parse_raw_data(self) -> Mapping[str, Union[str, UUID]]:
            pass

    def get_server_info(self):
        return self.MediaserverInfo(self._get_server_info())

    def get_server_id(self):
        return self.get_server_info().server_id

    def get_server_name(self):
        return self.get_server_info().server_name

    @abstractmethod
    def get_module_info(self):
        pass

    @abstractmethod
    def _get_version(self):
        pass

    def get_version(self):
        raw_version = self._get_version()
        return Version(raw_version)

    def server_older_than(self, branch: str) -> bool:
        server_version = Version(self._get_version())
        branch_version = self._branch_as_tuple(branch)
        return server_version[:len(branch_version)] < branch_version

    def server_newer_than(self, branch: str) -> bool:
        server_version = Version(self._get_version())
        branch_version = self._branch_as_tuple(branch)
        return server_version[:len(branch_version)] > branch_version

    @staticmethod
    def _branch_as_tuple(name: str) -> tuple:
        prefix = 'vms_'
        if not name.startswith(prefix):
            raise RuntimeError('Only vms_* branches are supported')
        try:
            version = tuple(int(v) for v in name[len('vms_'):].split('.', 3))
        except ValueError:
            raise RuntimeError(f'Unexpected branch name: {name}')
        if len(version) < 2:
            raise RuntimeError("Branch must contain at least major and minor version numbers")
        return version

    def get_cloud_host(self):
        return self.http_get('/api/moduleInformation')['cloudHost']

    _setup_logger = _logger.getChild('setup')

    def get_credentials(self) -> Credentials:
        if isinstance(self._auth_handler, HttpBearerAuthHandler):
            token = self._auth_handler.get_token()
        else:
            token = None
        return Credentials(
            username=self._user,
            password=self._password,
            auth_type=self.auth_type,
            token=token,
            )

    @abstractmethod
    def _make_local_setup_request(
            self,
            system_name: str,
            password: str,
            system_settings: Mapping[str, Any],
            settings_preset: Optional[str],
            ):
        pass

    @property
    @abstractmethod
    def _version_specific_system_settings(self) -> Mapping[str, Any]:
        pass

    def setup_local_system(
            self,
            system_settings: Optional[Mapping[str, Any]] = None,
            basic_and_digest_auth_required: bool = False,
            settings_preset: Optional[str] = None,
            name: Optional[str] = None,
            ):
        if name is None:
            system_name = 'local-' + self._netloc.replace('.', '-').replace(':', '--')
        else:
            system_name = name
        basic_and_digest_auth_should_be_enabled = (
            (self._basic_and_digest_auth_required or basic_and_digest_auth_required) and self.basic_and_digest_auth_disabled())
        if basic_and_digest_auth_should_be_enabled:
            self.enable_basic_and_digest_auth_for_admin()
        system_settings = system_settings or {}
        system_settings = {
            'statisticsAllowed': 'true',
            # Time from the other mediaservers will be applied to the current one
            # if their time difference is greater than the epsilon time.
            # Set the minimum epsilon time to always apply the time.
            'syncTimeEpsilon': '1',  # Milliseconds
            **self._version_specific_system_settings,
            **system_settings}
        _logger.info('Setup local system on %s (system settings: %s)', self, system_settings)
        password = 'WellKnownPassword2'
        try:
            self._make_local_setup_request(system_name, password, system_settings, settings_preset)
        except Forbidden as e:
            if 'Disabled insecure deprecated API' in str(e):
                self._enable_insecure_deprecated_api()
                self._make_local_setup_request(
                    system_name, password, system_settings, settings_preset)
        self.set_credentials(self._user, password)
        if basic_and_digest_auth_should_be_enabled:
            # After system setup, settings for admin are reset to their defaults.
            # Thus, Basic and Digest authentications should be enabled again.
            self.enable_basic_and_digest_auth_for_admin()
        started_at = time.monotonic()
        while True:
            if self.system_is_set_up():
                break
            if time.monotonic() - started_at > 30:
                raise TimeoutError("Timed out waiting for system to set up")
            time.sleep(2)
        _logger.info('Setup local system: complete, local system id: %s', self.get_local_system_id())

    def basic_and_digest_auth_disabled(self):
        credentials = self.get_credentials()
        digest_based_api = self.with_digest_auth(
            credentials.username, credentials.password)
        try:
            digest_based_api._request_with_required_authentication()
        except Unauthorized as e:
            if 'DisabledBasicAndDigest' not in str(e):
                raise
            return True
        return False

    def enable_basic_and_digest_auth_for_admin(self):
        credentials = self.get_credentials()
        session_based_api = self.with_local_bearer_auth(
            credentials.username, credentials.password)
        session_based_api.enable_basic_and_digest_auth_for_user(
            SYSTEM_ADMIN_USER_ID, credentials.password)

    def enable_basic_and_digest_auth_for_user(self, user_id, password):
        # isHttpDigestEnabled cannot be enabled without a password,
        # because it is needed to compute the hash.
        # Enabling Basic and Digest authentication is only possible since APIv1.
        version = 'v1' if self._version == 'v0' else self._version
        self.http_patch(f'rest/{version}/users/{_format_uuid(user_id)}', {
            'isHttpDigestEnabled': True,
            'password': password,
            })

    def switch_basic_and_digest_auth_for_ldap_user(self, user_id, enabled: bool):
        # For LDAP users, unlike local users, the password does not need to be passed.
        version = 'v1' if self._version == 'v0' else self._version
        self.http_patch(f'rest/{version}/users/{_format_uuid(user_id)}', {
            'isHttpDigestEnabled': enabled,
            })

    def _enable_insecure_deprecated_api(self):
        # Enabling insecure deprecated endpoints is only possible since APIv1.
        self.set_system_settings({'insecureDeprecatedApiEnabled': True})

    @abstractmethod
    def _detach_from_system(self):
        pass

    def detach_from_system(self):
        self._detach_from_system()
        self.set_credentials(self._user, _INITIAL_API_PASSWORD)

    @abstractmethod
    def _make_cloud_setup_request(
            self, system_name, cloud_system_id, auth_key, account_name, system_settings):
        pass

    def setup_cloud_system(self, cloud_account, system_settings=None) -> str:
        _logger.info('Setting up server as cloud system %s:', self)
        system_name = 'cloud-' + self._netloc.replace('.', '-').replace(':', '--')
        system_settings = system_settings or {}
        system_settings = {**system_settings, **self._version_specific_system_settings}
        bind_info = cloud_account.bind_system(system_name)
        basic_and_digest_auth_should_be_enabled = (
            self._basic_and_digest_auth_required and self.basic_and_digest_auth_disabled())
        if basic_and_digest_auth_should_be_enabled:
            self.enable_basic_and_digest_auth_for_admin()
        try:
            self._make_cloud_setup_request(
                system_name,
                bind_info.system_id,
                bind_info.auth_key,
                cloud_account.user_email,
                system_settings)
        except Forbidden as e:
            if 'Disabled insecure deprecated API' in str(e):
                self._enable_insecure_deprecated_api()
                self._make_cloud_setup_request(
                    system_name,
                    bind_info.system_id,
                    bind_info.auth_key,
                    cloud_account.user_email,
                    system_settings)
        if isinstance(self._auth_handler, HttpBearerAuthHandler):
            self._auth_handler = cloud_account.make_auth_handler(bind_info.system_id)
        else:
            self._auth_handler = self._auth_handler.with_credentials(
                cloud_account.user_email, cloud_account.password)
        if not self.credentials_work():
            raise RuntimeError("Cloud account cannot log in after setupCloudSystem")
        return bind_info.auth_key

    @abstractmethod
    def connect_system_to_cloud(self, auth_key, system_id, user_email):
        pass

    @abstractmethod
    def _detach_from_cloud(self, password, current_password):
        pass

    def detach_from_cloud(self, password, current_password):
        self._detach_from_cloud(password, current_password)
        # If a handler from the cloud or another server was used, it should be replaced
        # with a local one.
        self._auth_handler = self._make_auth_handler(_DEFAULT_API_USER, password, self.auth_type)

    def get_system_name(self) -> str:
        return self.get_system_settings()['systemName']

    @abstractmethod
    def get_system_settings(self):
        pass

    @abstractmethod
    def get_site_name(self) -> str:
        pass

    _known_bool_settings = {
        'arecontRtspEnabled',
        'auditTrailEnabled',
        'autoDiscoveryEnabled',
        'autoDiscoveryResponseEnabled',
        'cameraSettingsOptimization',
        'statisticsAllowed',
        'timeSynchronizationEnabled',
        }

    def _format_system_settings(self, system_settings):
        formatted_settings = {}
        for key, value in system_settings.items():
            if key not in self._known_bool_settings:
                formatted_settings[key] = value
                continue
            if value.lower() == 'true':
                formatted_settings[key] = True
            elif value.lower() == 'false':
                formatted_settings[key] = False
            else:
                raise RuntimeError(
                    f"{value!r} is not a valid bool representation for {key!r} bool setting.")
        return formatted_settings

    def set_system_settings(self, new_settings):
        credentials = self.get_credentials()
        session_based_api = self.with_local_bearer_auth(
            credentials.username, credentials.password)
        formatted_settings = self._format_system_settings(new_settings)
        version = 'v1' if self._version == 'v0' else self._version
        session_based_api.http_patch(
            f'rest/{version}/system/settings', formatted_settings)

    def rename_site(self, new_name: str):
        self.set_system_settings({f'{self._site_term}Name': new_name})

    def get_email_settings(self) -> _EmailSettings:
        system_settings = self.get_system_settings()
        if not self.server_older_than('vms_6.0'):
            email_settings = system_settings['emailSettings']
            if isinstance(email_settings, str):
                email_settings = json.loads(system_settings['emailSettings'])
            return _EmailSettings(
                connection_type=email_settings.get('connectionType'),
                email=email_settings.get('email'),
                password=email_settings.get('password'),
                server=email_settings.get('server'),
                signature=email_settings.get('signature'),
                support_address=email_settings.get('supportAddress'),
                user=email_settings.get('user'),
                )
        return _EmailSettings(
            connection_type=system_settings.get('smtpConnectionType'),
            email=system_settings.get('emailFrom'),
            password=system_settings.get('smtpPassword'),
            server=system_settings.get('smtpHost'),
            signature=system_settings.get('emailSignature'),
            support_address=system_settings.get('emailSupportEmail'),
            user=system_settings.get('smtpUser'),
            )

    def set_email_settings(
            self,
            *,
            connection_type: Optional[str] = None,
            email: Optional[str] = None,
            password: Optional[str] = None,
            server: Optional[str] = None,
            signature: Optional[str] = None,
            support_address: Optional[str] = None,
            user: Optional[str] = None,
            ):
        if not self.server_older_than('vms_6.0'):
            settings = {
                'connectionType': connection_type,
                'email': email,
                'password': password,
                'server': server,
                'signature': signature,
                'supportAddress': support_address,
                'user': user,
                }
            settings = {k: v for k, v in settings.items() if v is not None}
            settings = {'emailSettings': settings}
        else:
            settings = {
                'smtpConnectionType': connection_type,
                'emailFrom': email,
                'smtpPassword': password,
                'smtpHost': server,
                'emailSignature': signature,
                'emailSupportEmail': support_address,
                'smtpUser': user,
                }
            settings = {k: v for k, v in settings.items() if v is not None}
        self.set_system_settings(settings)

    @abstractmethod
    def get_local_system_id(self):
        pass

    def get_cloud_system_id(self):
        resource_params = self.list_all_resource_params()
        try:
            [param] = [p for p in resource_params if p['name'] == 'cloudSystemID']
        except ValueError:
            raise NotAttachedToCloud(f"Server {self} is not attached to cloud")
        return UUID(param['value'])

    def system_is_set_up(self):
        return self.get_local_system_id() != UUID(int=0)

    def set_local_system_id(self, new_id):
        self.http_get('/api/configure', params={'localSystemId': _format_uuid(new_id)})

    def change_admin_password(self, new_password):
        response = self.http_post('/api/configure', {
            'password': new_password,
            'currentPassword': self._password,
            })
        self.set_credentials(self._user, new_password)
        # VMS-29359: After admin password reset, its authorization methods are also reset.
        if self._basic_and_digest_auth_required and self.basic_and_digest_auth_disabled():
            self.enable_basic_and_digest_auth_for_admin()
        return response

    @abstractmethod
    def _save_server_attributes(self, server_id, attributes):
        pass

    @abstractmethod
    def list_servers(self):
        pass

    @abstractmethod
    def get_server(self, server_id):
        pass

    @abstractmethod
    def remove_server(self, server_id):
        pass

    @staticmethod
    def _make_dummy_mediaserver_data(index):
        hosts = iter(ipaddress.ip_network('10.10.0.0/22'))
        ip_address = [next(hosts) for _ in range(index + 1)][-1]
        network_location = f'{ip_address}:7001'
        name = f'ft-mediaserver-{index}'
        auth_key = UUID(bytes=hashlib.md5(name.encode('ascii')).digest())
        return {
            'name': name,
            'id': f'8e25e200-0000-0000-0000-{index:012}',
            'parentId': str(UUID(int=0)),
            'panicMode': 'PM_None',
            'systemInfo': 'windows x64 win78',
            'systemName': name,
            'version': '3.0.0.0',
            'authKey': f'{{{auth_key}}}',
            'flags': 'SF_HasPublicIP',
            'apiUrl': network_location,
            'url': f'rtsp://{network_location}',
            'networkAddresses': network_location,
            'typeId': '{be5d1ee0-b92c-3b34-86d9-bca2dab7826f}',
            'osInfo': {
                'platform': 'linux_x64',
                'variant': 'ubuntu',
                'variantVersion': '16.04',
                'flavor': 'default',
                },
            }

    @abstractmethod
    def add_dummy_mediaserver(self, index):
        pass

    @abstractmethod
    def add_generated_mediaserver(self, primary, attributes=None):
        pass

    def wait_for_neighbors(self, expected_count):
        started_at = time.monotonic()
        while True:
            _logger.info("%r: Wait for %d neighbors", self, expected_count)
            if len(self.list_system_mediaserver_ids()) == expected_count + 1:
                break
            if time.monotonic() - started_at > 30:
                raise RuntimeError(
                    f"Neighbor count didn't reach {expected_count} for long")
            time.sleep(1)

    def wait_for_neighbors_status(self, expected_status, timeout_sec=10):
        started = time.monotonic()
        self_guid = self.get_server_id()
        while True:
            servers_statuses = self.list_system_mediaservers_status()
            actual_statuses = {k: v for k, v in servers_statuses.items() if k != self_guid}
            expected_statuses = {k: expected_status for k in servers_statuses if k != self_guid}
            self_status = servers_statuses[self_guid]
            expected_self = 'Online'
            _logger.debug(
                "Current server is %s; Other server statuses: %r", self_status, actual_statuses)
            if self_status == expected_self and actual_statuses == expected_statuses:
                return
            if time.monotonic() - started > timeout_sec:
                raise RuntimeError(
                    f"Some of servers are not having proper status after {timeout_sec}: "
                    f"Current server: {self_status!r}, should be 'Online';"
                    f"Other servers: {actual_statuses!r}, all should be {expected_status!r}")
            time.sleep(1)

    @abstractmethod
    def _get_timestamp_ms(self) -> int:
        pass

    def get_datetime(self) -> datetime:
        started_at = time.monotonic()
        time_response = self._get_timestamp_ms()
        round_trip = time.monotonic() - started_at
        received = datetime.fromtimestamp(float(time_response) / 1000., timezone.utc)
        _logger.debug("%r: Time %r; round-trip time %.3f", self, received, round_trip)
        return received

    @contextmanager
    def waiting_for_restart(self, timeout_sec: float = 10):
        """Ensure that actions under it cause a mediaserver restart.

        Save runtime id, yield to the client code that causes a restart.
        Then wait until server starts and reports the new runtime id.
        """
        old_runtime_id = self._get_server_runtime_id()
        _logger.info("%s: Runtime id before restart: %s", self, old_runtime_id)
        started_at = time.monotonic()

        yield

        failed_connections = 0

        while True:
            try:
                new_runtime_id = self._get_server_runtime_id()
            except MediaserverApiConnectionError as e:
                if time.monotonic() - started_at > timeout_sec:
                    raise RuntimeError(
                        "{}: Mediaserver hasn't started, caught {}, timed out."
                        .format(self, e))
                _logger.debug("%s: Expected failed connection: %r", self, e)
                failed_connections += 1
            except MediaserverApiHttpError as e:
                if time.monotonic() - started_at > 20:
                    raise RuntimeError(
                        f"{self}: Mediaserver hasn't started, caught {e}, timed out.")
                _logger.debug("%s: Expected failed request: %r", self, e)
            else:
                if new_runtime_id != old_runtime_id:
                    _logger.info(
                        "%s restarted successfully, new runtime id is %s",
                        self, new_runtime_id)
                    break

                if failed_connections > 0:
                    raise RuntimeError(
                        "{}: runtime id remains same after failed connections: {}".format(
                            self, old_runtime_id))

                if time.monotonic() - started_at > timeout_sec:
                    raise TimeoutError("{}: hasn't even stopped".format(self))

            time.sleep(5)

    def _get_server_runtime_id(self):
        return self.http_get('api/moduleInformation')['runtimeId']

    def restart(self, timeout_sec=10):
        with self.waiting_for_restart(timeout_sec=timeout_sec):
            self.request_restart()

    @abstractmethod
    def request_restart(self):
        pass

    @abstractmethod
    def _start_update(self, update_info):
        pass

    @abstractmethod
    def _update_info(self):
        pass

    @abstractmethod
    def _update_status(self):
        pass

    def prepare_update(self, update_info):
        self.start_update(update_info)
        self.wait_until_update_downloading()
        self.wait_until_update_ready_to_install()

    update_status_literal = 'code'
    update_error_literal = 'errorCode'

    def wait_until_update_ready_to_install(
            self,
            timeout_sec=120,
            ):
        self.wait_until_update_processed(timeout_sec=timeout_sec)
        for server in self.get_update_status().values():
            if server[self.update_status_literal] != 'readyToInstall':
                raise RuntimeError(
                    f"Unexpected update {self.update_status_literal}: "
                    f"{server[self.update_status_literal]}")
            if server[self.update_error_literal] != 'noError':
                raise RuntimeError(
                    f"Unexpected update error code: {server[self.update_error_literal]}")
            if server['progress'] != 0:
                raise RuntimeError(
                    f"Unexpected update progress: {server['progress']}")

    def start_update(self, update_info):
        update_info_prepared = self._prepare_update_info(update_info)
        self._start_update(update_info_prepared)
        started_at = time.monotonic()
        while True:
            if self._update_info_match(update_info_prepared):
                break
            if time.monotonic() - started_at > 3:
                raise RuntimeError("Couldn't get same update info back")
            time.sleep(0.2)

    @staticmethod
    @abstractmethod
    def _update_info_match(update_info):
        pass

    @staticmethod
    @abstractmethod
    def _prepare_update_info(update_info):
        pass

    @abstractmethod
    def cancel_update(self):
        pass

    def get_update_status(self, ignore_server_ids=()) -> Mapping[UUID, Mapping]:
        system_status = self._update_status()
        result = {}
        for server_status in system_status:
            server_id = UUID(server_status['serverId'])
            if server_id in ignore_server_ids:
                continue
            result[server_id] = {**server_status, 'serverId': server_id}
        return result

    def wait_until_update_processed(self, ignore_server_ids=(), timeout_sec=120):
        progress_states = ['starting', 'downloading', 'preparing']
        started_at = time.monotonic()
        while time.monotonic() - started_at <= timeout_sec:
            system_status = self.get_update_status(ignore_server_ids=ignore_server_ids).values()
            for server_status in system_status:
                if server_status[self.update_status_literal] in progress_states:
                    break
                # A server state can blink due to network issues or immediately
                # after the system starts.
                # See: https://networkoptix.atlassian.net/browse/VMS-52143
                if server_status[self.update_status_literal] in ['offline', 'idle']:
                    break
            else:
                return
            time.sleep(1)
        for server_status in self.get_update_status(ignore_server_ids=ignore_server_ids).values():
            if server_status[self.update_status_literal] == 'offline':
                raise RuntimeError('Server is offline. %r', server_status)
        raise RuntimeError('Update is in progress')

    def wait_until_update_downloading(self, ignore_server_ids=()):
        started_at = time.monotonic()
        while True:
            all_statuses = self.get_update_status(ignore_server_ids=ignore_server_ids)
            for status in all_statuses.values():
                if status[self.update_status_literal] in {'preparing', 'readyToInstall'}:
                    raise RuntimeError('Downloading already done')
                if status[self.update_status_literal] != 'downloading':
                    break
                if status['progress'] == 0:
                    break
            else:
                break
            if time.monotonic() - started_at > 10:
                raise RuntimeError('Update downloading not started')
            time.sleep(0.1)

    def install_update(self):
        # The installUpdate requires "peers" GET param.
        return self.http_post('api/installUpdate', {}, params={'peers': ''})

    def add_test_cameras(
            self,
            offset,
            count,
            address='127.0.0.100',
            parent_id=None,
            ) -> Sequence[Testcamera]:
        parent_id = parent_id if parent_id is not None else self.get_server_id()
        cameras = []

        for i in range(1, count + 1):
            raw_input = testcamera_raw_input(offset + i, address, _format_uuid(parent_id))
            camera_id = self._add_camera(raw_input)
            camera = Testcamera(camera_id, raw_input)
            cameras.append(camera)

        return cameras

    @abstractmethod
    def add_generated_camera(self, primary, attributes=None, params=None):
        pass

    @abstractmethod
    def rename_camera(self, camera_id, new_name):
        pass

    def _make_camera_stream_urls(self, camera_id):
        camera = self.get_camera(camera_id)
        before_extension, extension = camera.url.rsplit('.', 1)
        second_stream_url = f'{before_extension}-2.{extension}'
        return {'1': camera.url, '2': second_stream_url}

    def set_secondary_stream(self, camera_id: UUID, stream_url: str):
        camera = self.get_camera(camera_id)
        self._set_camera_streams(camera_id, camera.url, stream_url)

    def enable_secondary_stream(self, camera_id: UUID):
        camera = self.get_camera(camera_id)
        before_extension, extension = camera.url.rsplit('.', 1)
        second_stream_url = f'{before_extension}-2.{extension}'
        self._set_camera_streams(camera_id, camera.url, second_stream_url)

    @abstractmethod
    def _set_camera_streams(self, camera_id: UUID, primary_stream_url: str, secondary_stream_url: str):
        pass

    @staticmethod
    def _nvr_id_key(physical_id):
        """Method for NVR channel sorting.

        NVR second and following channels has physical id like
        <NVR MAC address>_channel=<channel_index>.
        """
        [_physical_id, has_channel, channel] = physical_id.partition('_channel=')
        return int(channel) if has_channel else 1

    @abstractmethod
    def _start_manual_cameras_search(self, camera_url, credentials):
        pass

    @abstractmethod
    def _get_manual_cameras_search_state(self, search_id):
        pass

    @abstractmethod
    def _add_manual_cameras_to_db(self, searcher_camera_list, credentials):
        pass

    @staticmethod
    def _make_camera_auth_params(user=None, password=None):
        auth_params = {}
        if user is not None:
            auth_params['user'] = user
        if password is not None:
            auth_params['password'] = password
        if len(auth_params) == 1:
            raise ValueError(
                "Credentials must contain user and password, but only "
                f"{str(auth_params).strip('{}')} is provided.")
        return auth_params

    class CameraNotFound(Exception):
        pass

    def _add_camera_manually(
            self,
            camera_url,
            user: Optional[str] = None,
            password: Optional[str] = None,
            ) -> Generator[None, None, Sequence[BaseCamera]]:
        """Generator that represents multi-step camera adding process."""
        auth_params = self._make_camera_auth_params(user, password)
        search_id = self._start_manual_cameras_search(camera_url, auth_params)
        _logger.debug("Manual camera %s: search started, process id %s", camera_url, search_id)
        yield
        while True:  # Time is controlled by the consumer.
            [manual_cameras, status] = self._get_manual_cameras_search_state(search_id)
            current_progress = int(status['current'])
            total_progress = int(status['total'])
            state = status['state']
            _logger.debug(
                "Manual camera %s: progress %d/%d, state %s, count %d",
                camera_url,
                current_progress, total_progress,
                state,
                len(manual_cameras))
            if current_progress >= total_progress:
                if state != 3 and state != 'Finished':  # Differs for different versions
                    raise RuntimeError(
                        f"Manual camera search progress is {current_progress} / {total_progress} "
                        f"but state is {state} whereas should be 3 or Finished")
                if not manual_cameras:
                    raise self.CameraNotFound(
                        f"Manual camera search progress is {current_progress} / {total_progress} "
                        "but no cameras found")
                break
            yield
        unique_ids = list(manual_cameras.keys())
        if len(unique_ids) > 1:
            # Order matters when adding NVR with multiple channels
            unique_ids.sort(key=self._nvr_id_key)
        # Camera is not added instantly, poll ec2/getCamerasEx.
        _logger.debug("Manual camera %s: found, unique id %s", camera_url, unique_ids)
        self._add_manual_cameras_to_db(list(manual_cameras.values()), auth_params)
        yield
        # Id param supports different types of id.
        while True:
            found_cameras = {c.physical_id: c for c in self.list_cameras()}
            if set(unique_ids).issubset(set(found_cameras)):
                break
            yield
        cameras = [found_cameras[u] for u in unique_ids]
        _logger.info("Manual camera %s: added, resources %s", camera_url, cameras)
        return cameras

    @abstractmethod
    def add_manual_camera_sync(
            self,
            camera_url: str,
            user: Optional[str] = None,
            password: Optional[str] = None,
            ) -> Sequence[BaseCamera]:
        pass

    def add_cameras_manually(
            self,
            *camera_urls: str,
            # No scenarios when cameras with different credentials are bulk-added at the moment
            user: str = None,
            password: str = None,
            timeout_s=60,
            ) -> Generator[None, None, Sequence[BaseCamera]]:
        search_started_at = time.monotonic()
        searches = {}
        _logger.info("Attempt to manually add %d devices", len(camera_urls))
        for url in camera_urls:
            searches[url] = self._add_camera_manually(
                camera_url=url,
                user=user,
                password=password,
                )
            next(searches[url])
        added_cameras = []
        while True:
            yield
            for url in list(searches.keys()):
                try:
                    next(searches[url])
                except StopIteration as e:
                    del searches[url]
                    added_cameras.extend(e.value)
                except self.CameraNotFound:
                    raise
            if not searches:
                _logger.info("Finished manually adding cameras")
                return added_cameras
            elapsed_time_s = time.monotonic() - search_started_at
            if elapsed_time_s > timeout_s:
                raise TimeoutError(
                    f"Manually adding devices timed out after {elapsed_time_s}.1f/{timeout_s}s")

    @abstractmethod
    def _add_camera(self, primary):
        pass

    @abstractmethod
    def _modify_camera(self, camera_id, primary):
        pass

    @abstractmethod
    def _save_camera_attributes(self, camera_id, attributes):
        pass

    @abstractmethod
    def _save_camera_attributes_list(self, camera_ids, attributes):
        pass

    def set_camera_parent(self, camera_id, parent_id):
        self._modify_camera(camera_id, {'parentId': _format_uuid(parent_id)})

    def set_camera_failover_priority(self, camera_id, priority):
        self._save_camera_attributes(camera_id, {'failoverPriority': priority})

    def set_camera_preferred_parent(self, camera_id, server_id):
        self._save_camera_attributes(
            camera_id, {'preferredServerId': _format_uuid(server_id)})

    def enable_recording(self, camera_id, clear_schedule=False):
        attributes = {'scheduleEnabled': True}
        if clear_schedule:
            schedule_tasks = [
                {
                    'bitrateKbps': 0,
                    'dayOfWeek': day_of_week,
                    'endTime': 86400,
                    'fps': 0,
                    'metadataTypes': 'none',
                    'startTime': 0,
                    'recordingType': RecordingType.NEVER.value,
                    }
                for day_of_week in [1, 2, 3, 4, 5, 6, 7]
                ]
            attributes['scheduleTasks'] = schedule_tasks
        self._save_camera_attributes(camera_id, attributes)

    def start_recording(
            self, *camera_ids,
            fps=15, no_storages_ok=False, stream_quality='high',
            single_request=False,
            ):
        _logger.info("Recording: start: %r", camera_ids)
        if not no_storages_ok:
            all_storages = self.list_storages(ignore_offline=True)
            if not any(s.is_writable for s in all_storages):
                raise RuntimeError(f"No writable storages: {all_storages}")
        try:
            self.setup_recording(
                *camera_ids,
                fps=fps,
                stream_quality=stream_quality,
                enable_recording=True,
                single_request=single_request)
        except Forbidden:
            raise RecordingStartFailed(
                "Failed to start recording on camera. This may be due to the lack of a license "
                "or access to the camera or server, the lack of user permissions, "
                "or some other reasons")

    def setup_recording(
            self, *camera_ids, fps=15, stream_quality='high',
            recording_type: RecordingType = RecordingType.ALWAYS,
            motion_params: MotionParameters = None, enable_recording=False,
            single_request=False,
            ):
        if not isinstance(fps, (float, int)) or not 2 <= fps <= 120:
            raise ValueError(
                f"FPS value {fps} isn't a real number within sensible bounds; "
                "this may cause surprising behavior: "
                "e.g., passing None results in a frame each 1.5-2 seconds")
        schedule_tasks = [
            {
                'afterThreshold': 5,
                'beforeThreshold': 5,
                'dayOfWeek': day_of_week,
                'endTime': 86400,
                'fps': fps,
                'recordAudio': False,
                'recordingType': recording_type.value,
                'startTime': 0,
                'streamQuality': stream_quality,
                }
            for day_of_week in [1, 2, 3, 4, 5, 6, 7]]
        if recording_type == RecordingType.MOTION_ONLY:
            schedule_tasks = [
                {'metadataTypes': 'motion', **task}  # It's 'none' by default after VMS-29962
                for task in schedule_tasks
                ]
        attributes = {'scheduleTasks': schedule_tasks}
        if motion_params is not None:
            attributes["motionMask"] = motion_params.motion_mask
            if motion_params.record_after_motion_sec is not None:
                attributes["recordAfterMotionSec"] = motion_params.record_after_motion_sec
            if motion_params.record_before_motion_sec is not None:
                attributes["recordBeforeMotionSec"] = motion_params.record_before_motion_sec
        attributes['scheduleEnabled'] = enable_recording
        if single_request:
            self._save_camera_attributes_list(camera_ids, attributes)
        else:
            for camera_id in camera_ids:
                self._save_camera_attributes(camera_id, attributes)

    def stop_recording(self, camera_id):
        _logger.info("Recording: stop: %r", camera_id)
        self._save_camera_attributes(camera_id, {'scheduleEnabled': False})

    @contextmanager
    def camera_recording(self, camera_id):
        if not camera_id:
            raise ValueError("Camera ID is empty, is it registered?")
        self.start_recording(camera_id)
        try:
            yield
        finally:
            self.stop_recording(camera_id)
            started_at = time.monotonic()
            while True:
                camera_ex, = self.http_get('ec2/getCamerasEx', {'id': camera_id})
                if camera_ex['status'] != CameraStatus.RECORDING:
                    break
                if time.monotonic() - started_at > 30:
                    raise TimeoutError("Timed out waiting for camera to stop recording")
                time.sleep(2)

    def _switch_stream_recording(self, camera_id, stream, enable_recording: bool):
        assert stream in ('primary', 'secondary')
        options = {'primary': 'dontRecordPrimaryStream', 'secondary': 'dontRecordSecondaryStream'}
        self.set_camera_resource_params(camera_id, {options[stream]: '0' if enable_recording else '1'})

    def enable_stream_recording(self, camera_id, stream: str):
        self._switch_stream_recording(camera_id, stream, True)

    def disable_stream_recording(self, camera_id, stream):
        self._switch_stream_recording(camera_id, stream, False)

    def enable_audio(self, camera_id):
        self._save_camera_attributes(camera_id, {'audioEnabled': True})

    def disable_audio(self, camera_id):
        self._save_camera_attributes(camera_id, {'audioEnabled': False})

    @abstractmethod
    def _set_backup_quality_for_newly_added_cameras(self, low: bool, high: bool):
        pass

    def set_backup_quality_for_newly_added_cameras(self, low: bool, high: bool):
        if not low and not high:
            raise RuntimeError("At least one stream must be selected for backup")
        self._set_backup_quality_for_newly_added_cameras(low, high)

    def _set_cameras_backup_mode(self, camera_ids, is_enabled):
        attributes = {
            'backupPolicy': 'on' if is_enabled else 'off',
            # 0 (high and low), 1 (high), 2 (low), 3 (default).
            # Don't force any quality type here. The default should be used.
            'backupQuality': '3',
            }
        self._save_camera_attributes_list(camera_ids, attributes)

    def enable_backup_for_cameras(self, camera_ids):
        self._set_cameras_backup_mode(camera_ids, is_enabled=True)

    def disable_backup_for_cameras(self, camera_ids):
        self._set_cameras_backup_mode(camera_ids, is_enabled=False)

    @abstractmethod
    def enable_backup_for_newly_added_cameras(self):
        pass

    @abstractmethod
    def disable_backup_for_newly_added_cameras(self):
        pass

    def camera_backup_is_enabled(self, camera_id):
        camera = self.get_camera(camera_id)
        if camera.backup_policy == 'byDefault':
            global_backup_settings = self.get_system_settings()['backupSettings']
            return global_backup_settings['backupNewCameras']
        return camera.backup_policy == 'on'

    def set_motion_type_for_cameras(self, camera_ids, motion_type: MotionType, use_lexical=False):
        motion_type_value = str(motion_type.value) if not use_lexical else motion_type.name.lower()
        attributes = {'motionType': motion_type_value}
        self._save_camera_attributes_list(camera_ids, attributes)

    def rebuild_main_archive(self):
        self._rebuild_archive(main_pool=_StorageType.MAIN)

    def rebuild_backup_archive(self):
        self._rebuild_archive(main_pool=_StorageType.BACKUP)

    def _rebuild_archive(self, main_pool):
        self._start_rebuild_archive(main_pool)
        timeout_sec = 30
        started_at = time.monotonic()
        while True:
            if not self._rebuild_archive_in_progress(main_pool):
                return
            if time.monotonic() - started_at > timeout_sec:
                raise TimeoutError('Timed out waiting for archive to rebuild')
            time.sleep(1)

    def _start_rebuild_archive(self, main_pool: _StorageType):
        self.http_post('api/rebuildArchive', {
            'mainPool': main_pool,
            'action': 'start',
            })

    def _rebuild_archive_in_progress(self, main_pool: _StorageType) -> bool:
        response = self.http_post('api/rebuildArchive', {'mainPool': main_pool})
        known_states = ('RebuildState_None', 'RebuildState_FullScan', 'RebuildState_PartialScan')
        if response['state'] not in known_states:
            raise RuntimeError(f"Unknown rebuild archive state: {response['state']}")
        return response['state'] != 'RebuildState_None'

    @abstractmethod
    def _list_recorded_periods(self, camera_ids, periods_type=None, detail_level_ms=None):
        pass

    @staticmethod
    def _sort_recorded_periods(camera_periods: Iterable[TimePeriod]):
        return sorted(camera_periods, key=lambda p: p.start)

    def _list_recorded_periods_unchecked(self, camera_ids, periods_type, detail_level_ms):
        as_dict = self._list_recorded_periods(camera_ids, periods_type, detail_level_ms)
        periods = []
        for camera_id in camera_ids:
            camera_periods = []
            for p in as_dict.get(camera_id, []):
                period = TimePeriod(
                    start_ms=int(p['startTimeMs']),
                    duration_ms=self._get_duration_ms(p),
                    )
                camera_periods.append(period)
            periods.append(self._sort_recorded_periods(camera_periods))
        return periods

    @staticmethod
    def _get_duration_ms(period_raw):
        return int(period_raw['durationMs']) if int(period_raw['durationMs']) != -1 else None

    @staticmethod
    def _skip_recorded_periods(listed, to_skip):
        result = []
        for camera_periods, camera_skip_periods in zip(listed, to_skip):
            new_camera_periods = []
            for period in camera_periods:
                if period not in camera_skip_periods:
                    new_camera_periods.append(period)
            result.append(new_camera_periods)
        return result

    @staticmethod
    def _all_recorded_periods_complete(result):
        for periods_for_camera in result:
            for period in periods_for_camera:
                if not period.complete:
                    return False
        return True

    class RecordedPeriodsType(NamedTuple):

        RECORDING = 0
        MOTION = 1
        ANALYTICS = 2

    def list_recorded_periods(
            self,
            camera_ids,
            timeout_sec=15.0,
            incomplete_ok=True,
            empty_ok=True,
            skip_periods=None,
            periods_type=None,
            detail_level_ms=None,
            ) -> Sequence[Sequence[TimePeriod]]:
        assert skip_periods is None or len(skip_periods) == len(camera_ids)
        camera_ids = [
            camera_id if isinstance(camera_id, UUID) else UUID(camera_id)
            for camera_id in camera_ids]
        started_at = time.monotonic()
        while True:
            result = self._list_recorded_periods_unchecked(camera_ids, periods_type, detail_level_ms)
            if skip_periods is not None:
                result = self._skip_recorded_periods(result, skip_periods)
            if incomplete_ok or self._all_recorded_periods_complete(result):
                if empty_ok or all(result):
                    return result
            if time.monotonic() - started_at > timeout_sec:
                raise TimeoutError(
                    f"Got deficient TimePeriods after timeout {timeout_sec} seconds."
                    f"(incomplete_ok={incomplete_ok}, empty_ok={empty_ok})")
            time.sleep(1)

    def _get_camera_param_manifest(self, camera_id):
        return self.http_get(
            'api/getCameraParamManifest', {'cameraId': str(camera_id)})

    def _set_camera_advanced_params(self, camera_id, values):
        self.http_get('api/setCameraParam', {'cameraId': str(camera_id), **values})

    def configure_audio(self, camera_id, codec):
        manifest = self._get_camera_param_manifest(camera_id)
        if 'Hanwha' in manifest['name']:
            path = ['Audio Input']
            codec_param_name = 'Codec'
        else:  # Axis and others (if such support audio).
            path = ['Audio', 'Input Settings']
            codec_param_name = 'Audio Encoding'
        audio_group = _get_manifest_group(manifest, path)
        codec_param_id = _get_manifest_param_id(audio_group, codec_param_name)
        self._set_camera_advanced_params(camera_id, {codec_param_id: codec})

    def configure_video(self, camera_id, profile, codec, resolution, fps=None, bitrate_kbps=None):
        manifest = self._get_camera_param_manifest(camera_id)
        if 'Hanwha' in manifest['name']:
            path = ['Streaming', profile.title() + ' Stream']
            fps_param_name = 'Frame Rate'
        else:  # Axis, ONVIF and others.
            path = ['Video Streams Configuration', profile.title()]
            fps_param_name = 'FPS'
        profile_group = _get_manifest_group(manifest, path)
        values = {}
        values[_get_manifest_param_id(profile_group, 'Codec')] = codec
        values[_get_manifest_param_id(profile_group, 'Resolution')] = resolution
        if fps is not None:
            values[_get_manifest_param_id(profile_group, fps_param_name)] = fps
        if bitrate_kbps is not None:
            values[_get_manifest_param_id(profile_group, 'Bitrate')] = bitrate_kbps
        self._set_camera_advanced_params(camera_id, values)

    def get_server_statistics(self):
        return self.http_get('/api/statistics')

    def get_server_uptime_sec(self) -> float:
        server_statistics = self.get_server_statistics()
        return float(server_statistics['uptimeMs']) / 1000

    def get_hdd_statistics(self):
        server_statistics = self.get_server_statistics()['statistics']
        current_disk_stats = {}
        for info in server_statistics:
            if info['deviceType'] != 'StatisticsHDD':
                continue
            current_disk_stats[info['description']] = info['value']
        return current_disk_stats

    @abstractmethod
    def remove_camera(self, camera_id):
        pass

    def remove_resource(self, resource_id):
        self.http_post('ec2/removeResource', dict(id=_format_uuid(resource_id)))

    def set_camera_credentials(self, camera_id, login, password):
        data = ':'.join([login, password])
        self.set_camera_resource_params(camera_id, {'credentials': data})

    def list_ip_addresses(self) -> list[ipaddress.IPv4Address]:
        all_interfaces = self.get_metrics('network_interfaces')
        server_id = self.get_server_id()
        result = []
        for [[id_, _], values] in all_interfaces.items():
            if id_ != server_id:
                continue
            if values.get('state') != 'Up':
                continue
            result.append(ipaddress.ip_address(values['display_address']))
        return result

    def list_system_mediaservers_status(self):
        servers_list = self.list_servers()
        ids = {info.id: info.status for info in servers_list}
        return ids

    def list_system_mediaserver_ids(self):
        return set(self.list_system_mediaservers_status().keys())

    @abstractmethod
    def get_auth_data(self):
        """Returns the authentication data required for a merge request with another mediaserver."""
        pass

    def get_merge_history(self):
        return self.http_get('/ec2/getSystemMergeHistory')

    @abstractmethod
    def merge_in_progress(self, timeout_sec):
        pass

    @abstractmethod
    def _request_merge(
            self,
            remote_url: str,
            remote_auth,
            take_remote_settings=False,
            merge_one_server=False):
        pass

    def request_merge(
            self,
            remote_url: str,
            remote_auth,
            take_remote_settings=False,
            merge_one_server=False,
            ):
        # When many servers are merged, there is server visible from others.
        # This server is passed as remote. That's why it's higher in loggers hierarchy.
        try:
            return self._request_merge(
                remote_url,
                remote_auth,
                take_remote_settings=take_remote_settings,
                merge_one_server=merge_one_server)
        except MediaserverApiHttpError as e:
            raise ExplicitMergeError(
                self, remote_url, e.vms_error_code, e.vms_error_string)

    def recording_is_enabled(self, camera_id):
        return self.get_camera(camera_id).schedule_is_enabled

    @staticmethod
    def _format_camera_id(camera_id, is_uuid, validate_logical_id):
        if is_uuid:
            # physical id is used in RCT
            camera_id = _format_uuid(camera_id)
        if isinstance(camera_id, int):
            if validate_logical_id:
                if camera_id < 1:
                    raise ValueError("Logical ID has to be a natural number")
            camera_id = str(camera_id)
        if not isinstance(camera_id, str):
            raise TypeError(f"Unsupported camera ID type {type(camera_id)}")
        return camera_id

    @abstractmethod
    def get_camera(self, camera_id):
        pass

    @abstractmethod
    def list_cameras(self) -> Collection[BaseCamera]:
        pass

    def get_camera_by_base_url(self, base_url: str) -> BaseCamera:
        cameras = self.list_cameras()
        for camera in cameras:
            if camera.url.startswith(base_url):
                return camera
        raise RuntimeError(f"No camera with address {base_url} found on the server")

    def get_camera_by_name(self, camera_name: str) -> BaseCamera:
        cameras = self.list_cameras()
        for camera in cameras:
            if camera.name == camera_name:
                return camera
        raise RuntimeError(f"No camera {camera_name} found on the server")

    def get_camera_history(self, camera_id):
        params = {'cameraId': camera_id, 'startTime': 0, 'endTime': 'now'}
        response = self.http_get('ec2/cameraHistory', params)
        history_items = response[0]['items']
        history_ids = [UUID(item['serverGuid']) for item in history_items]
        timestamps = [float(item['timestampMs']) / 1000 for item in history_items]
        if timestamps != sorted(timestamps):
            raise RuntimeError(f"Camera history not sorted: {history_items}")
        return history_ids

    def list_camera_history(self):
        response = self.http_get('ec2/getCameraHistoryItems')
        return [_CameraHistory(data) for data in response]

    def _get_camera_thumbnail(
            self,
            camera_id,
            height: Optional[int] = None,
            when: Optional[datetime] = None,
            ) -> ByteString:
        params = {'cameraId': _format_uuid(camera_id)}
        if height is not None:
            params['height'] = height
        if when is not None:
            time_formatted = when.isoformat(sep='T', timespec='milliseconds')
            params['time'] = time_formatted
            params['method'] = 'precise'  # It may be a bit costly though
        return self._http_download('ec2/cameraThumbnail', params)

    def get_lightweight_camera_thumbnail(self, camera_id) -> ByteString:
        # Set minimal size to get lightweight image file.
        return self._get_camera_thumbnail(camera_id, height=128)

    def get_camera_frame(
            self,
            camera_id: Union[str, UUID],
            when: Optional[datetime] = None,
            ) -> ByteString:
        """Get a video frame in JPEG with original resolution at precise time.

        From the mediaserver point of view, this is the same as thumbnail,
        hence the endpoint name. There are multiple parameters in the request.
        For now, only known use cases are implemented.

        The method is intended for external usage.
        """
        if isinstance(camera_id, UUID):
            camera_id = str(camera_id)
        if when is not None and when.tzinfo is not None:
            raise ValueError(
                "Frame time should be naive, i.e. without a timezone; "
                "it's in the local timezone of the mediaserver")
        if when is not None:
            try:
                return self._get_camera_thumbnail(camera_id, when=when)
            except NoContent:
                raise RuntimeError(
                    f"Cannot get a frame from camera {camera_id} at {when}; "
                    "perhaps, there's no archive at the specified time")
        else:
            try:
                return self._get_camera_thumbnail(camera_id)
            except NoContent:
                raise RuntimeError(
                    f"Cannot get a frame from camera {camera_id}; "
                    "perhaps, there's no archive and the camera is offline")

    def wait_for_camera_status(self, camera_id, status, timeout_sec=30):
        camera_id = _format_uuid(camera_id)
        started_at = time.monotonic()
        while True:
            actual_status = self.get_camera(camera_id).status
            if actual_status == status:
                _logger.info("Camera %s went %s", camera_id, actual_status)
                return
            passed_sec = time.monotonic() - started_at
            _logger.info(
                "Camera %s is %s, %.1f/%.1f sec passed waiting for %s",
                camera_id, actual_status, passed_sec, timeout_sec, status)
            if passed_sec > timeout_sec:
                raise TimeoutError(timeout_sec, (
                    f"Camera {camera_id} is still {actual_status} "
                    f"but not {status} after {timeout_sec} sec"))
            time.sleep(1)

    def wait_for_cameras_synced(self, neighbour_api_list, timeout_sec=30):
        started_at = time.monotonic()
        while time.monotonic() - started_at <= timeout_sec:
            camera_ids = [camera.id for camera in self.list_cameras()]
            neighbour_camera_ids = []
            for api in neighbour_api_list:
                neighbour_camera_ids.append([camera.id for camera in api.list_cameras()])
            if all(camera_ids == ids for ids in neighbour_camera_ids):
                break
            time.sleep(1)
        else:
            raise RuntimeError(f"Failed to sync cameras in {timeout_sec} seconds")

    def add_event_rule(
            self, event_type: str, event_state: EventState, action: RuleAction, event_resource_ids=(),
            event_condition: Optional[EventCondition] = None,
            ):
        event_condition = EventCondition() if event_condition is None else event_condition
        response = self.http_post('ec2/saveEventRule', dict(
            **action.fields,
            aggregationPeriod=0,
            comment='',
            disabled=False,
            eventCondition=event_condition.to_string(),
            eventResourceIds=[*event_resource_ids],
            eventState=event_state.value,
            eventType=event_type,
            id='{%s}' % uuid1(),
            schedule='',
            system=False,
            ))
        return UUID(response['id'])

    def remove_event_rule(self, rule_id) -> None:
        self.http_post('ec2/removeEventRule', {'id': _format_uuid(rule_id, strict=True)})

    def set_event_rule_action(self, rule_id, action: RuleAction):
        self.http_post(
            'ec2/saveEventRule', {'id': _format_uuid(rule_id, strict=True), **action.fields})

    def modify_event_rule(
            self,
            rule_id: UUID,
            event_type: Optional[str] = None,
            event_state: Optional[EventState] = None,
            action: Optional[RuleAction] = None,
            event_resource_ids: Collection[str] = (),
            event_condition: Optional[EventCondition] = None):
        params = {
            'id': _format_uuid(rule_id),
            'eventResourceIds': event_resource_ids}
        if event_type is not None:
            params['eventType'] = event_type
        if event_state is not None:
            params['eventState'] = event_state.value
        if action is not None:
            params.update(action.fields)
        if event_condition is not None:
            params['eventCondition'] = event_condition.to_string()
        response = self.http_post('ec2/saveEventRule', params)
        return UUID(response['id'])

    def disable_event_rule(self, rule_id: UUID):
        self.http_post('ec2/saveEventRule', {'id': _format_uuid(rule_id), 'disabled': True})

    def list_event_rules(self):
        return [Rule(data) for data in self.http_get('ec2/getEventRules')]

    def get_event_rule(self, rule_id):
        event_rule_list = self.http_get(
            'ec2/getEventRules', {'id': _format_uuid(rule_id, strict=True)})
        return Rule(event_rule_list[0]) if event_rule_list else None

    def reset_event_rules(self):
        self.http_post('ec2/resetEventRules', {})

    def create_event(self, state: Optional[EventState] = None, **params):
        if state is not None:
            params['state'] = state.value
        self.http_post('api/createEvent', params)

    def list_events(
            self,
            camera_id: UUID | str | None = None,
            type_: str | None = None,
            ) -> Collection[Mapping[str, Any]]:
        query = {
            'from': '2000-01-01',
            'to': '3000-01-01',
            'cameraId': _format_uuid(camera_id) if camera_id is not None else None,
            'event_type': type_}
        return self.http_get('api/getEvents', {k: v for k, v in query.items() if v is not None})

    def execute_ptz(self, camera_id, command, **kwargs):
        return self.http_get('api/ptz', dict(
            cameraId=camera_id, command=command + 'PtzCommand', **kwargs))

    def get_brand(self):
        reply = self.http_get('api/moduleInformation')
        return reply['brand']

    @abstractmethod
    def add_license(self, license_key: str, license_block: str):
        pass

    @abstractmethod
    def _activate_license(self, license_key: str):
        pass

    def activate_license(self, license_key: str):
        attempts_left = 6
        while True:
            try:
                self._activate_license(license_key)
            except MediaserverApiHttpError as e:
                if e.vms_error_id == 'missingParameter':
                    raise LicenseAddError('missingParameter', e.vms_error_string)
                if 'Parameter' in e.vms_error_string and 'missing' in e.vms_error_string:
                    raise LicenseAddError('missingParameter', e.vms_error_string)
                if attempts_left > 0:
                    attempts_left -= 1
                    _logger.warning(
                        "Error occurred on license activation: %s; Attempts left: %d",
                        e.vms_error_string,
                        attempts_left)
                    continue
                raise RuntimeError(
                    f"Cannot activate license: {e.vms_error_string}. "
                    f"This may be caused by changes in DNS, wrong entries in etc/hosts "
                    f"or nameserver reachability problem.")
            else:
                break

    def activate_nvr_channel_license(self, nvr_channel_id):
        # There's 'licenseUsed' bool attribute for each camera, but it does nothing. To activate
        # NVR channel license we need to enable recording (same as for camera). It does not
        # affect any of the NVR recording settings, but makes NVR archive accessible in the VMS.
        # 'scheduleTasks' value is indifferent in this case.
        self.enable_recording(nvr_channel_id)

    @abstractmethod
    def remove_license(self, license_key: str):
        pass

    @abstractmethod
    def _list_licenses(self):
        pass

    def list_licenses(self) -> list[_License]:
        for _ in range(5):
            response = self._list_licenses()
            try:
                licenses = [_License(raw_license) for raw_license in response]
            except _IncompleteLicenseBlock as e:
                _logger.debug(e)
                time.sleep(2)
                continue
            else:
                return licenses
        raise RuntimeError('Failed to get licenses from %s', self)

    def get_full_info(self):
        return _FullInfo(
            cameras=self.list_cameras(),
            camera_history=self.list_camera_history(),
            layouts=self.list_layouts(),
            licenses=self.list_licenses(),
            rules=self.list_event_rules(),
            servers=self.list_servers(),
            storages=self.list_all_storages(),
            users=self.list_users(),
            videowalls=self.list_videowalls(),
            )

    @abstractmethod
    def _get_server_flags(self):
        pass

    def has_public_ip(self):
        return 'SF_HasPublicIP' in self._get_server_flags()

    def get_transaction_log(self):
        return self.http_get('ec2/getTransactionLog', timeout=180)

    @abstractmethod
    def _dump_database(self):
        pass

    def dump_database(self) -> bytes:
        database = self._dump_database()
        return database

    @abstractmethod
    def _restore_database(self, database):
        pass

    def restore_database(self, database: bytes):
        self._restore_database(database)

    def list_hwids(self):
        server_id = self.get_server_id()
        servers_info = {
            UUID(server['serverId']): server['hardwareIds']
            for server in self.http_get('ec2/getHardwareIdsOfServers')}
        return servers_info[server_id]

    @abstractmethod
    def list_bookmarks(self, camera_id: UUID) -> Collection[_BaseBookmark]:
        pass

    @abstractmethod
    def get_bookmark(self, camera_id: UUID, bookmark_id: UUID) -> _BaseBookmark:
        pass

    @abstractmethod
    def add_bookmark(
            self,
            camera_id: UUID,
            name: str,
            start_time_ms: Optional[int] = None,
            duration_ms: Optional[int] = None,
            description: Optional[str] = None,
            ) -> UUID:
        pass

    @abstractmethod
    def set_bookmark_duration(self, bookmark: _BaseBookmark, duration_ms: int):
        pass

    @abstractmethod
    def remove_bookmark(self, bookmark: _BaseBookmark):
        pass

    @abstractmethod
    def update_bookmark_description(
            self, camera_id: UUID, bookmark_id: UUID, new_description: str):
        pass

    def add_bookmark_from_time_period(self, camera_id: UUID, name: str, period: TimePeriod):
        self.add_bookmark(
            camera_id=camera_id,
            name=name,
            start_time_ms=period.start_ms,
            duration_ms=int(period.duration_sec * 1000),
            )

    def become_primary_time_server(self):
        """Set up time synchronization scheme with a primary time server.

        The primary server synchronizes with the Internet or, if not connected,
        with the local machine time.
        The other servers in the system synchronize with the primary.
        """
        server_id = str(self.get_server_id())
        self.http_post('ec2/forcePrimaryTimeServer', {'id': server_id})

    def turn_off_primary_time_server(self):
        """Set up independent time synchronization.

        Every server in the system independently synchronizes with the Internet
        or, if not connected, with the local machine time.
        """
        self.http_post('ec2/forcePrimaryTimeServer', {})

    def get_primary_time_server_id(self) -> UUID:
        return UUID(self.get_system_settings()['primaryTimeServer'])

    def is_primary_time_server(self):
        return self.get_primary_time_server_id() == self.get_server_id()

    @abstractmethod
    def _get_servers_timestamp(self):
        pass

    def wait_for_time_synced(self):
        timeout_sec = 10
        threshold = timedelta(seconds=1)
        started_at = time.monotonic()
        while time.monotonic() - started_at < timeout_sec:
            servers_time = []
            for server_timestamp in self._get_servers_timestamp():
                server_time = datetime.fromtimestamp(float(server_timestamp) / 1000, timezone.utc)
                servers_time.append(server_time)
            if max(servers_time) - min(servers_time) < threshold:
                break
            _logger.debug("Continue waiting for servers time synchronized.")
            time.sleep(1)
        else:
            raise RuntimeError(
                f"Timed out ({timeout_sec} seconds) waiting for servers time synchronized.")

    def event_queue(self, wait_for_start_server=True):
        return EventQueue(self, wait_for_start_server)

    def audit_trail(self, skip_initial_records=True):
        return AuditTrail(self, skip_initial_records=skip_initial_records)

    @abstractmethod
    def rename_server(self, new_server_name, server_id=None):
        pass

    @abstractmethod
    def _list_storage_objects(self) -> list[Storage]:
        pass

    def list_storages(
            self, within_path=None, timeout_sec=40.0, ignore_offline=False, storage_type=None):
        # VMS-16364: API call can hang for 5 minutes if server has inaccessible SMB storage
        if within_path is not None:
            # Strip trailing "/" and "\"
            within_path = within_path.rstrip('/\\')

        started_at = time.monotonic()
        while True:
            storages = self._list_storage_objects()
            result = []
            for storage in storages:
                if not ignore_offline:
                    if 'beingChecked' in storage.status:
                        _logger.debug("Retry: %r: beingChecked", storage)
                        break
                if storage_type is not None and storage.type != storage_type:
                    continue
                if within_path is not None:
                    if not storage.path.startswith(within_path):
                        _logger.debug("Not in %s: %s", within_path, storage.path)
                        continue
                    if within_path != storage.path:
                        if storage.path[len(within_path)] not in ['\\', '/']:
                            continue
                if not ignore_offline and storage.id == UUID(int=0):
                    _logger.debug("Retry: %r: zero id", storage)
                    break
                result.append(storage)
            else:
                if result:
                    return result
            if time.monotonic() - started_at > timeout_sec:
                raise StorageUnavailable("Some storages are still not ready after timeout")
            time.sleep(1)

    def list_storages_info_brief(self):
        return self.http_get('ec2/getStorages')

    @abstractmethod
    def list_all_storages(self):
        pass

    @abstractmethod
    def _add_storage(self, primary):
        pass

    @abstractmethod
    def _modify_storage(self, storage_id, primary):
        pass

    @abstractmethod
    def get_storage(self, storage_id: UUID) -> Optional[Storage]:
        pass

    @abstractmethod
    def add_storage(self, path_or_url, type, is_backup=False):
        pass

    def add_smb_storage(
            self,
            address,
            share,
            username=None,
            password=None,
            is_backup=False,
            init_timeout=60,
            ):
        pure_url = 'smb://{}/{}'.format(address, share)
        if not username:
            if password:
                raise ValueError("No username but password provided")
            url = pure_url
        else:
            auth = username + ':' + password if password else username
            url = 'smb://{}@{}/{}'.format(auth, address, share)
        storage_id = self.add_storage(url, 'smb', is_backup)
        self.list_storages(pure_url, timeout_sec=init_timeout)
        return storage_id

    @abstractmethod
    def add_dummy_smb_storage(self, index, parent_id=None):
        pass

    def add_generated_storage(self, primary):
        return self._add_storage(primary)

    def rename_storage(self, storage_id, new_name):
        self._modify_storage(storage_id, {'name': new_name})

    @abstractmethod
    def remove_storage(self, storage_id):
        pass

    def enable_storage(self, storage_id):
        self._modify_storage(storage_id, {'usedForWriting': True})

    def set_up_new_storage(self, mount_point, is_backup=False) -> tuple[Storage, Storage]:
        # Mediaserver supports hot-pluggable and network disks. There is no need to restart
        # mediaserver to use these disks as storages. But if connected on
        # working mediaserver, storages appear disabled and have null ID.
        # To get ID it's needed either restart mediaserver or call 'ec2/saveStorage'
        # with its path as 'url' argument and server ID as 'parentId'.
        _logger.debug("Set up storage: %s", mount_point)
        # Make sure mount_point is correct path.
        [discovered_storage] = self.list_storages(str(mount_point), ignore_offline=True)
        parent_id = self.get_server_id()
        self._add_storage({
            'name': f'Storage {mount_point}',
            'url': discovered_storage.path,
            'usedForWriting': True,
            'storageType': discovered_storage.type,
            'parentId': str(parent_id),
            'isBackup': is_backup,
            'spaceLimit': discovered_storage.reserved_space,
            })
        [saved_storage] = self.list_storages(str(mount_point))
        return discovered_storage, saved_storage

    def disable_storage(self, storage_id):
        self._modify_storage(storage_id, {'usedForWriting': False})

    def reserve_storage_space(self, storage_id, reserve_bytes: int):
        _logger.debug("Set storage %s reserved space: %s", storage_id, reserve_bytes)
        self._modify_storage(storage_id, {'spaceLimit': str(reserve_bytes)})

    def request_allocate_storage_for_backup(self, storage_id):
        _logger.debug("Allocate storage %s for backup", storage_id)
        if isinstance(storage_id, str):
            storage_id = UUID(storage_id)
        self._modify_storage(storage_id, {'isBackup': True})

    def allocate_storage_for_backup(self, storage_id):
        self.request_allocate_storage_for_backup(storage_id)
        # Wait for storage to become ready
        started_at = time.monotonic()
        while time.monotonic() - started_at < 60.0:
            storage = self.get_storage(storage_id)
            if storage.is_online:
                return
            _logger.debug("Wait for storage %s come online", storage_id)
            time.sleep(6)
        raise RuntimeError("Storage didn't come online after timeout")

    @abstractmethod
    def allocate_storage_for_analytics(self, storage_id):
        pass

    @abstractmethod
    def get_metadata_storage_id(self):
        pass

    _weekdays = ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')

    def _backup_bitrate_bps_schedule(self, start_hour, finish_hour, days):
        # Since 5.0, backup schedule is configured via backupBitrateBytesPerSecond,
        # which has the following structure:
        # [
        #     {
        #         "key": { "day": "DAY_OF_WEEK", "hour": HOUR },
        #         "value": BYTES_PER_SECOND
        #     },
        #     ...
        # ]
        # For any day-hour position, a missing value means "unlimited bitrate",
        # and a zero value means "don't perform backup"
        schedule = []
        for day in self._weekdays:
            for hour in range(24):
                if day in days and start_hour <= hour <= finish_hour:
                    continue
                schedule.append({'key': {'day': day, 'hour': hour}, 'value': 0})
        return {'backupBitrateBytesPerSecond': schedule}

    def setup_backup_by_schedule(self, start_hour, finish_hour, days=_weekdays):
        if not 0 <= start_hour <= 23:
            raise ValueError("start_hour must be in range [0, 23].")
        if not 0 <= finish_hour <= 23:
            raise ValueError("finish_hour must be in range [0, 23].")
        schedule = self._backup_bitrate_bps_schedule(start_hour, finish_hour, days)
        self._save_server_attributes(self.get_server_id(), schedule)

    def clear_backup_schedule(self):
        schedule = []
        for day in self._weekdays:
            for hour in range(24):
                schedule.append({'key': {'day': day, 'hour': hour}, 'value': 0})
        self._save_server_attributes(
            self.get_server_id(), {'backupBitrateBytesPerSecond': schedule})

    @abstractmethod
    def wait_for_backup_finish(self):
        pass

    @abstractmethod
    def _enable_failover(self, max_cameras):
        pass

    def enable_failover(self, max_cameras=128):
        self._enable_failover(max_cameras)

    def get_conf_doc(self):
        # Named "conf" to match Mediaserver.update_mediaserver_conf.
        # "Settings" may refer to system settings or to ec2/getSettings.
        response = self.http_get('/api/settingsDocumentation')
        return {item['name']: item for item in response['settings']}

    @abstractmethod
    def _restore_state(self):
        pass

    def restore_state(self):
        with self.waiting_for_restart():
            self._restore_state()
        # If a handler from the cloud or another server was used, it should be replaced
        # with a local one.
        self._auth_handler = self._make_auth_handler('admin', 'admin', self.auth_type)

    @abstractmethod
    def _add_user_group(self, primary):
        pass

    @abstractmethod
    def _modify_user_group(self, group_id, primary):
        pass

    def _make_user_group_primary_params(
            self,
            name: Optional[str] = None,
            permissions: Optional[Iterable[str]] = None,
            parent_group_ids: Optional[Iterable[UUID]] = None,
            ):
        if parent_group_ids is not None:
            parent_group_ids = [str(group_id) for group_id in parent_group_ids]
        return self._prepare_params({
            "permissions": self._format_permissions(permissions),
            "name": name,
            "parentGroupIds": parent_group_ids,
            })

    def add_user_group(
            self,
            name: str,
            permissions: Collection[str],
            parent_group_ids: Optional[Iterable[UUID]] = None,
            ) -> UUID:
        primary = self._make_user_group_primary_params(
            name=name,
            permissions=permissions,
            parent_group_ids=parent_group_ids,
            )
        return self._add_user_group(primary)

    def add_generated_user_group(self, primary):
        return self._add_user_group(primary)

    @abstractmethod
    def get_user_group(self, group_id):
        pass

    def modify_user_group(self, group_id, name=None, permissions=None):
        primary = self._make_user_group_primary_params(name=name, permissions=permissions)
        self._modify_user_group(group_id, primary)

    @abstractmethod
    def remove_user_group(self, group_id):
        pass

    @abstractmethod
    def set_group_access_rights(self, group_id, resource_ids):
        pass

    def set_camera_logical_id(self, camera_id, logical_id: int):
        if not isinstance(logical_id, int):
            raise TypeError(
                "Although logicalId is represented by a string on the Server side, essentially it "
                "is a natural number: integer > 0 is expected.")
        if logical_id < 1:
            raise ValueError(
                "Setting logicalId < 1 will remove logicalId from the camera. If that is what you "
                "intend to do consider using remove_logical_id method instead.")
        self._save_camera_attributes(camera_id, {'logicalId': str(logical_id)})

    def remove_camera_logical_id(self, camera_id):
        self._save_camera_attributes(camera_id, {'logicalId': '0'})

    def set_camera_archive_days(
            self,
            camera_id,
            min_archive_days=1,
            max_archive_days=1,
            auto=False,
            ):
        if auto:
            min_archive_days = max_archive_days = -1
        self._save_camera_attributes(camera_id, {
            'minArchiveDays': min_archive_days,  # vms_5.0 and earlier
            'maxArchiveDays': max_archive_days,  # vms_5.0 and earlier
            'minArchivePeriodS': min_archive_days * 24 * 60 * 60,  # vms_5.0_patch
            'maxArchivePeriodS': max_archive_days * 24 * 60 * 60,  # vms_5.0_patch
            })

    def list_resource_params(self, resource_id):
        return self.http_get('ec2/getResourceParams', {'id': _format_uuid(resource_id)})

    def list_all_resource_params(self):
        return self.http_get('ec2/getResourceParams')

    def _set_resource_params(self, resource_id: UUID, params: Mapping[str, str]):
        params = [
            {'resourceId': _format_uuid(resource_id), 'name': k, 'value': v}
            for k, v in params.items()]
        self.http_post('ec2/setResourceParams', params)

    def set_camera_resource_params(self, camera_id: UUID, params: Mapping[str, str]):
        """Names of resource params are not specific to API version and are treated as opaque."""
        self._set_resource_params(camera_id, params)

    def _get_raw_metric_values(self):
        return self.http_get('ec2/metrics/values')

    def get_metrics(self, resource_type, *metric_path):
        metrics_values = MetricsValues(self._get_raw_metric_values())
        return metrics_values.get_metrics(resource_type, *metric_path)

    def get_metrics_for_data_analysis(self):
        metrics_values = MetricsValues(self._get_raw_metric_values())
        return metrics_values.list_of_dicts_with_known_keys()

    def wait_for_metric(self, resource_type, *metric_path, timeout_sec=30, expected=None):
        started_at = time.monotonic()
        while True:
            metric = self.get_metrics(resource_type, *metric_path)
            if metric == expected:
                _logger.debug(
                    "The actual metric was received after %.1f seconds", time.monotonic() - started_at)
                return
            if time.monotonic() - started_at > timeout_sec:
                raise RuntimeError(
                    f"After {timeout_sec} seconds metric {resource_type!r}: {metric_path!r} "
                    f"is {metric!r}, expected {expected!r}")
            time.sleep(1)

    def _get_raw_metric_alarms(self):
        return self.http_get('ec2/metrics/alarms')

    def list_metrics_alarms(self):
        alarms = self._get_raw_metric_alarms()
        result = defaultdict(list)

        for resource_type in alarms:
            for resource_id in alarms[resource_type]:
                for category in alarms[resource_type][resource_id]:
                    for subcategory in alarms[resource_type][resource_id][category]:
                        key = (resource_type, UUID(resource_id), category, subcategory)
                        alarm_list = alarms[resource_type][resource_id][category][subcategory]
                        result[key] = [
                            Alarm(level=alarm['level'], text=alarm['text'])
                            for alarm in alarm_list]

        return result

    def disable_event_rules(self):
        """Disable event rules.

        It's useful to avoid clashes with rules created by test, mediaserver
        doesn't write records for disabled event rules to event log.
        """
        for event_rule in self.list_event_rules():
            self.http_post('ec2/saveEventRule', dict(
                id=_format_uuid(event_rule.id),
                disabled=True,
                ))

    def has_resource(self, method, **kw):
        def is_subset(subset, superset):
            return all(item in superset.items() for item in subset.items())

        resources = [
            r
            for r in self.http_get('ec2/' + method)
            if is_subset(kw, r)
            ]
        return len(resources) != 0

    def _test_ldap_settings(self, settings: _LdapSettings):
        return self.http_post('api/testLdapSettings', settings.as_dict(), timeout=60)

    def list_users_from_ldap_server(
            self,
            host: str,
            admin_dn: str,
            admin_password: str,
            search_base: Optional[Collection[LdapSearchBase]] = None,
            ):
        ldap_settings = _LdapSettingsV0(host, admin_dn, admin_password, search_base)
        return self._test_ldap_settings(ldap_settings)

    def check_ldap_server(
            self,
            host: str,
            admin_dn: str,
            admin_password: str,
            search_base: Optional[Collection[LdapSearchBase]] = None,
            ):
        ldap_settings = _LdapSettingsV0(host, admin_dn, admin_password, search_base)
        self._test_ldap_settings(ldap_settings)

    def set_ldap_settings(
            self,
            host: str,
            admin_dn: str,
            admin_password: str,
            search_base: Optional[Collection[LdapSearchBase]] = None,
            ):
        settings = _LdapSettingsV0(host, admin_dn, admin_password, search_base)
        self.set_system_settings(settings.as_dict())

    def set_ldap_password_expiration_period(self, period_sec: int):
        self.set_system_settings({'ldapPasswordExpirationPeriodMs': period_sec * 1000})

    def sync_ldap_users(self, timeout: float = DEFAULT_HTTP_TIMEOUT):
        self.http_post('api/mergeLdapUsers', {}, timeout=timeout)

    def disable_time_sync(self):
        """Disable time synchronization with internet and across mediaservers the system.

        If timeSynchronizationEnabled is false, then each mediaserver starts to synchronize time
        with it's own OS local time.
        """
        self.set_system_settings({'timeSynchronizationEnabled': 'false'})

    def time_sync_with_internet_is_enabled(self):
        """Return information about whether the synchronizeTimeWithInternet flag is set.

        The value of this flag is calculated according to the following rules:
        - if primaryTimeServer is not set and timeSynchronizationEnabled is true,
        then the value is true;
        - otherwise it is false.
        """
        primary_time_server_id = self.get_primary_time_server_id()
        if int(primary_time_server_id) != 0:
            return False
        time_sync_enabled = self.get_system_settings().get('timeSynchronizationEnabled', 'true')
        if time_sync_enabled != 'true':
            return False
        return True

    def get_web_page_by_name(self, name: str) -> WebPage:
        for w in self.list_web_pages():
            if w.name() == name:
                return w
        raise RuntimeError(f"Cannot find webpage {name!r}")

    @abstractmethod
    def list_web_pages(self):
        pass

    @abstractmethod
    def get_web_page(self, page_id):
        pass

    @abstractmethod
    def add_web_page(self, name, url):
        pass

    @abstractmethod
    def modify_web_page(self, page_id, name=None, url=None):
        pass

    @abstractmethod
    def remove_web_page(self, page_id):
        pass

    _layout_type_id = UUID('e02fdf56-e399-2d8f-731d-7a457333af7f')

    @abstractmethod
    def add_layout(self, name, type_id=None):
        pass

    @abstractmethod
    def add_layout_with_resource(self, name, resource_id):
        pass

    @abstractmethod
    def add_shared_layout_with_resource(self, layout_1_name: str, resource_id: UUID) -> UUID:
        pass

    @abstractmethod
    def add_generated_layout(self, primary):
        pass

    @abstractmethod
    def list_layouts(self):
        pass

    @abstractmethod
    def get_layout(self, layout_id):
        pass

    @abstractmethod
    def remove_layout(self, layout_id):
        pass

    def add_statistics_server(self, statserver_url):
        self.set_system_settings({'statisticsReportServerApi': statserver_url})

    def set_statistics_time_cycle(self, delay):
        self.set_system_settings({'statisticsReportTimeCycle': f'{delay}'})

    def enable_statistics(self):
        self.set_system_settings({'statisticsAllowed': 'true'})

    def disable_statistics(self):
        self.set_system_settings({'statisticsAllowed': 'false'})

    def trigger_statistics_report(self):
        response = self.http_get('ec2/triggerStatisticsReport')
        if response['status'] != 'initiated':
            raise RuntimeError("ec2/triggerStatisticsReport: not initiated")
        return response

    class DeviceAnalyticsSettings:

        def __init__(self, raw: Mapping):
            self.model = raw['settingsModel']
            self.values = raw['settingsValues']
            self.stream = raw['analyzedStreamIndex']
            self.message_to_user = raw.get('messageToUser')

    def get_device_analytics_settings(self, device_id, engine_id):
        data = self.http_get('/ec2/deviceAnalyticsSettings', params={
            'deviceId': _format_uuid(device_id),
            'analyticsEngineId': _format_uuid(engine_id)})
        return self.DeviceAnalyticsSettings(data)

    def set_device_analytics_settings(
            self,
            device_id: UUID,
            engine_id: UUID,
            settings_values: Mapping[str, Any],
            ) -> DeviceAnalyticsSettings:
        raw_settings = self.http_post('/ec2/deviceAnalyticsSettings', {
            'deviceId': _format_uuid(device_id),
            'analyticsEngineId': _format_uuid(engine_id),
            'settingsValues': settings_values})
        return self.DeviceAnalyticsSettings(raw_settings)

    def set_device_analytics_analyzed_stream(
            self,
            device_id: UUID,
            engine_id: UUID,
            stream: Literal['primary', 'secondary'],
            ) -> None:
        self.http_post('/ec2/deviceAnalyticsSettings', {
            'deviceId': _format_uuid(device_id),
            'analyticsEngineId': _format_uuid(engine_id),
            'analyzedStreamIndex': stream,
            })

    def _list_enabled_analytics_engines(self, camera_id) -> Iterable[UUID]:
        resource_params = self.list_resource_params(camera_id)
        for resource_param in resource_params:
            engines_param = resource_param['name'] == 'userEnabledAnalyticsEngines'
            engines_param_value = resource_param['value']
            if engines_param and engines_param_value:
                return [UUID(engine_id) for engine_id in json.loads(engines_param_value)]
        return []

    @abstractmethod
    def _get_raw_analytics_engines(self):
        pass

    def get_analytics_engine_collection(self) -> AnalyticsEngineCollection:
        raw_engines = self._get_raw_analytics_engines()
        return AnalyticsEngineCollection(raw_engines)

    def _set_enabled_analytics_engines(self, camera_id, engine_ids: Iterable[UUID]):
        prepared_engine_ids = json.dumps([str(engine_id) for engine_id in engine_ids])
        self.set_camera_resource_params(
            camera_id, {'userEnabledAnalyticsEngines': prepared_engine_ids})

    def enable_device_agent(self, engine: AnalyticsEngine, camera_id: UUID) -> None:
        """Enables device agent of a plugin for given engine_name.

        A device agent is an entity that represents an analytics plugin that
        analyzes the video from a specific camera.
        """
        self._set_enabled_analytics_engines(camera_id, [engine.id()])
        started = time.monotonic()
        timeout_sec = 5
        while True:
            if engine.id() in self._list_enabled_analytics_engines(camera_id):
                return
            if time.monotonic() > started + timeout_sec:
                raise RuntimeError(
                    f"Device Agent {engine.name()} for camera {camera_id} was "
                    f"not enabled after {timeout_sec}s")
            time.sleep(1)

    def disable_analytics_for_camera(self, camera_id):
        self._set_enabled_analytics_engines(camera_id=camera_id, engine_ids=[])

    def get_analytics_engine_settings(self, engine_id: UUID) -> AnalyticsEngineSettings:
        data = self.http_get(
            path='/ec2/analyticsEngineSettings',
            params={'analyticsEngineId': _format_uuid(engine_id)},
            )
        return AnalyticsEngineSettings(data)

    def set_analytics_engine_settings(
            self,
            engine_id,
            settings_values: dict,
            ):
        self.http_post('/ec2/analyticsEngineSettings', {
            'analyticsEngineId': _format_uuid(engine_id),
            'settingsValues': settings_values,
            })

    def notify_engine_active_setting_changed(
            self, engine_id, engine_settings: AnalyticsEngineSettings,
            setting_name: str, new_setting_value: str = None, param_values: Mapping = None):
        settings_values = engine_settings.values
        if new_setting_value is not None:
            settings_values = {**settings_values, setting_name: new_setting_value}
        body = {
            'analyticsEngineId': _format_uuid(engine_id),
            'activeSettingName': setting_name,
            'settingsModel': engine_settings.model,
            'settingsValues': settings_values,
            }
        if param_values is not None:
            body = {'paramValues': param_values, **body}
        data = self.http_post('ec2/notifyAnalyticsEngineActiveSettingChanged', body)
        return AnalyticsEngineSettings(data)

    def notify_device_active_setting_changed(
            self, camera_id, engine_id, agent_settings: DeviceAnalyticsSettings,
            setting_name: str, new_setting_value: Optional[str] = None,
            param_values: Mapping = None):
        settings_values = agent_settings.values
        if new_setting_value is not None:
            settings_values = {**settings_values, setting_name: new_setting_value}
        body = {
            'deviceId': _format_uuid(camera_id),
            'analyticsEngineId': _format_uuid(engine_id),
            'activeSettingName': setting_name,
            'settingsModel': agent_settings.model,
            'settingsValues': settings_values,
            }
        if param_values is not None:
            body = {'paramValues': param_values, **body}
        data = self.http_post('ec2/notifyDeviceAnalyticsActiveSettingChanged', body)
        return self.DeviceAnalyticsSettings(data)

    def get_analytics_track(self, track_id, need_full_track=False) -> AnalyticsTrack:
        params = {'objectTrackId': _format_uuid(track_id)}
        if need_full_track:
            params = {**params, 'needFullTrack': True}
        [raw_track] = self.http_get('/ec2/analyticsLookupObjectTracks', params=params)
        return AnalyticsTrack(raw_track)

    def list_analytics_objects_tracks(
            self, params=None, with_positions=False) -> Sequence[AnalyticsTrack]:
        response = self.http_get('/ec2/analyticsLookupObjectTracks', params=params)
        result = [AnalyticsTrack(track) for track in response]
        result = sorted(result, key=lambda k: k.time_period().start_ms)
        if not with_positions:
            return result
        tracks_with_positions = []
        for track in result:
            tracks_with_positions.append(
                self.get_analytics_track(track.track_id(), need_full_track=True))
        return tracks_with_positions

    @abstractmethod
    def _best_shot_image_http_download(self, camera_id: str, track_id: str) -> bytes:
        pass

    def get_analytics_track_best_shot_image(self, camera_id, track_id) -> bytes:
        _logger.info("Fetch best shot for camera %s, track %s", camera_id, track_id)
        camera_id_formatted = _format_uuid(camera_id)
        track_id_formatted = _format_uuid(track_id)
        timeout_sec = 10
        started_at = time.monotonic()
        while True:
            try:
                return self._best_shot_image_http_download(camera_id_formatted, track_id_formatted)
            except NoContent:
                pass
            elapsed_time_sec = time.monotonic() - started_at
            message = (
                f"Camera {camera_id_formatted}, track {track_id_formatted}: "
                f"best shot is not available after {elapsed_time_sec}/{timeout_sec} sec")
            if elapsed_time_sec > timeout_sec:
                raise TimeoutError(message)
            _logger.debug("%s; wait 1 sec and retry", message)
            time.sleep(1)

    @abstractmethod
    def _title_image_http_download(self, camera_id: str, track_id: str) -> bytes:
        pass

    def get_analytics_track_title_image(self, camera_id: UUID, track_id: UUID) -> bytes:
        _logger.info("Fetch title image for camera %s, track %s", camera_id, track_id)
        camera_id_formatted = _format_uuid(camera_id)
        track_id_formatted = _format_uuid(track_id)
        timeout = 10
        started_at = time.monotonic()
        while True:
            try:
                return self._title_image_http_download(camera_id_formatted, track_id_formatted)
            except NoContent:
                pass
            elapsed_time = time.monotonic() - started_at
            message = (
                f"Camera {camera_id_formatted}, track {track_id_formatted}: "
                f"title image is not available after {elapsed_time}/{timeout} sec")
            _logger.info(message)
            if elapsed_time > timeout:
                raise RuntimeError(message)
            _logger.debug("%s; wait 1 sec and retry", message)
            time.sleep(1)

    @abstractmethod
    def execute_analytics_action(
            self,
            engine_id: UUID,
            action_id: str,
            object_track_id: UUID,
            camera_id: UUID,
            timestamp: int,
            params: Optional[Mapping] = None,
            ) -> Mapping[str, Union[str, bool]]:
        pass

    def list_audit_trail_records(self):
        # There is no such endpoint in the new API yet (VMS-23159)
        records = self.http_get('api/auditLog')
        return [
            AuditTrail.AuditRecord(
                type=record_data["eventType"],
                params=record_data["params"],
                resources=[UUID(res) for res in record_data["resources"]],
                created_time_sec=record_data["createdTimeSec"],
                range_start_sec=record_data["rangeStartSec"],
                range_end_sec=record_data["rangeEndSec"],
                )
            for record_data in records
            ]

    def get_plugin_info(self, plugin_name):
        response = self.http_get('/ec2/pluginInfo')
        system_plugin_info = {
            UUID(server_id): server_data for server_id, server_data in response.items()}
        server_plugin_info = system_plugin_info[self.get_server_id()]
        for plugin_info in server_plugin_info:
            if plugin_info['name'].lower() == plugin_name.lower():
                return plugin_info
        raise RuntimeError(f"No plugin {plugin_name!r} found for Server {self.get_server_id()}")

    def get_statistics_report(self):
        server_id = self.get_server_id()
        full_report = self.http_get('ec2/getStatisticsReport')
        [server_report] = [
            r for r in full_report['mediaservers'] if UUID(r['id']) == server_id]
        additional_params = {p['name']: p['value'] for p in server_report['addParams']}
        public_ip = additional_params['publicIp']
        if 'hddList' in additional_params:
            hdd_list = [hdd.strip() for hdd in additional_params['hddList'].split(',')]
        else:
            hdd_list = []
        backup_start = server_report.get('backupStart')
        if backup_start is None:
            backup_start = 0
        backup_bitrate_bps = server_report.get('backupBitrateBytesPerSecond')
        if backup_bitrate_bps is None:
            backup_bitrate_bps = []
        return StatisticsReport(
            id=UUID(server_report['id']),
            system_id=UUID(full_report['systemId']),
            parent_id=UUID(server_report['parentId']),
            plugin_info=server_report['pluginInfo'],
            hdd_list=hdd_list,
            physical_memory=int(additional_params['physicalMemory']),
            product_name=additional_params['productNameShort'],
            public_ip=public_ip,
            publication_type=additional_params['publicationType'],
            cpu_architecture=additional_params['cpuArchitecture'],
            cpu_model=additional_params['cpuModelName'],
            flags=set(server_report['flags'].split('|')),
            full_version=additional_params['fullVersion'],
            max_cameras=server_report['maxCameras'],
            status=server_report['status'],
            system_runtime=additional_params['systemRuntime'],
            version=server_report['version'],
            backup_start=backup_start,
            backup_type=server_report.get('backupType'),
            backup_days_of_week=server_report.get('backupDaysOfTheWeek'),
            backup_duration=server_report.get('backupDuration'),
            backup_bitrate=server_report.get('backupBitrate'),
            backup_bitrate_bps=backup_bitrate_bps,
            )

    def set_push_notification_language(self, language):
        if self.server_newer_than('vms_5.0'):
            self.set_system_settings({'cloudNotificationsLanguage': language})
        else:
            self.set_system_settings({'pushNotificationsLanguage': language})

    @abstractmethod
    def change_cameras_group_name(self, camera_ids, new_group_name):
        pass

    def check_system_ids_before_merge(self, servants: Iterable[MediaserverApi]):
        master_system_id = self.get_local_system_id()
        if master_system_id == UUID(int=0):
            raise RuntimeError(f"Master system on {self} is not set up")
        for servant in servants:
            servant_system_id = servant.get_local_system_id()
            if servant_system_id == UUID(int=0):
                raise RuntimeError(f"Servant system on {servant} is not set up")
            if servant_system_id == master_system_id:
                raise RuntimeError(
                    f"{self} and {servant} are in one local system {master_system_id} already")

    @abstractmethod
    def merge_is_finished(
            self,
            merge_responses: Iterable[Mapping[str, Any]],
            merge_timeout_sec: float,
            ) -> bool:
        pass

    def wait_for_merge(
            self,
            servants: Iterable[MediaserverApi],
            merge_responses: Iterable[Mapping[str, Any]],
            timeout_sec=30,
            ):
        started_at = time.monotonic()
        while time.monotonic() - started_at < timeout_sec:
            if not self.merge_is_finished(merge_responses, timeout_sec):
                _logger.info("Merge is not finished on master %r", self)
                time.sleep(0.5)
                continue
            for servant in servants:
                if not servant.credentials_work():
                    _logger.info("Credentials are not working for %s", servant)
                    time.sleep(0.5)
                    break
                if not servant.merge_is_finished(merge_responses, timeout_sec):
                    _logger.info("Merge is not finished on servant %r", servant)
                    time.sleep(0.5)
                    break
            else:
                _logger.info(
                    "Merge is finished for master %s and servants %r", self, servants)
                return
        raise RuntimeError(
            f"Merge did not finished in {timeout_sec}; master {self}; servants {servants}")

    @abstractmethod
    def backup_is_enabled_for_newly_added_cameras(self):
        pass

    @abstractmethod
    def get_backup_quality_for_newly_added_cameras(self):
        pass

    @abstractmethod
    def get_camera_backup_quality(self, camera_id):
        pass

    def open_transaction_bus_websocket(self, timeout_sec=10):
        return self.open_websocket('ec2/transactionBus/websocket', timeout_sec=timeout_sec)

    def disable_device_agents(self, camera_id):
        _logger.info("Disabling all enabled Device Agent for camera %s", camera_id)
        self.set_camera_resource_params(camera_id, {'userEnabledAnalyticsEngines': ''})
        started = time.monotonic()
        timeout_sec = 5
        while time.monotonic() - started < timeout_sec:
            if not self._list_enabled_analytics_engines(camera_id):
                _logger.info("All Device Agents for camera %s were disabled", camera_id)
                return
        raise RuntimeError(f"Some engines are enabled after {timeout_sec}s")

    @abstractmethod
    def list_analytics_periods(self, camera_id):
        pass

    @abstractmethod
    def list_motion_periods(self, camera_id):
        pass

    def add_virtual_camera(self, name):
        response = self.http_post('api/virtualCamera/add', {'name': name})
        return UUID(response['id'])

    @contextmanager
    def virtual_camera_locked(self, camera_id):
        token = self._lock_virtual_camera(camera_id)
        yield token
        self._release_virtual_camera(camera_id, token)

    def _lock_virtual_camera(self, camera_id) -> UUID:
        user_id = self._get_current_user_id()
        # Lock the camera for an extended period to avoid having to periodically renew the lock
        # using the api/virtualCamera/extend endpoint while the camera is in use.
        ttl_ms = 15 * 60 * 1_000
        response = self.http_post('api/virtualCamera/lock', {
            'cameraId': _format_uuid(camera_id),
            'ttl': ttl_ms,
            'userId': _format_uuid(user_id),
            })
        return UUID(response['token'])

    def _release_virtual_camera(self, camera_id, token: UUID):
        self.http_post('api/virtualCamera/release', {
            'cameraId': _format_uuid(camera_id),
            'token': _format_uuid(token),
            })

    def upload_to_virtual_camera(self, camera_id, file_path, lock_token, start_time_ms):
        upload_id = self._upload_file(file_path)
        self.http_post('api/virtualCamera/consume', {
            'cameraId': _format_uuid(camera_id),
            'startTime': str(start_time_ms),
            'token': _format_uuid(lock_token),
            'uploadId': upload_id,
            })
        timeout_sec = 60
        started_at = time.monotonic()
        while True:
            status = self._get_virtual_camera_status(camera_id)
            _logger.debug("Progress of adding video to virtual camera: %d", status['progress'])
            if status['consuming'] is False:
                return
            if time.monotonic() - started_at > timeout_sec:
                raise RuntimeError(
                    f"Failed to add video to virtual camera in {timeout_sec} seconds")
            time.sleep(1)

    def _get_virtual_camera_status(self, camera_id):
        return self.http_get('api/virtualCamera/status', params={
            'cameraId': _format_uuid(camera_id),
            })

    def _upload_file(self, file_path) -> str:
        name = file_path.name
        hash_md5 = hashlib.md5()
        chunk_size = 1024 * 1024  # Fastest
        with file_path.open('rb') as fp:
            size = 0
            while chunk_data := fp.read(chunk_size):
                hash_md5.update(chunk_data)
                size += len(chunk_data)
            md5_checksum = hash_md5.hexdigest()
            self._start_file_upload(name, size, md5_checksum)
            chunk_idx = 0
            fp.seek(0)
            while chunk_data := fp.read(chunk_size):
                self._http_request(
                    'PUT', f'api/downloads/{file_path.name}/chunks/{chunk_idx}',
                    headers={'Content-Type': 'application/octet-stream'},
                    data=chunk_data)
                chunk_idx += 1
        upload_status = self._get_file_upload_status(name)
        if upload_status != 'downloaded':
            raise RuntimeError(
                f"Failed to upload file {name!r}. Upload status is {upload_status!r}")
        return name

    def _start_file_upload(self, name, size, md5_checksum):
        self.http_post(f'api/downloads/{name}', {
            'chunkSize': f'{1024 ** 2}',
            'md5': f'{md5_checksum}',
            'recreate': 'true',
            'size': f'{size}',
            'upload': 'true',
            })

    def _get_file_upload_status(self, name):
        response = self.http_get(f'api/downloads/{name}/status')
        return response['status']

    def set_license_server(self, license_server_url: str):
        self.set_system_settings({'licenseServer': license_server_url})

    @abstractmethod
    def add_storage_encryption_key(self, password: str):
        pass

    @abstractmethod
    def list_db_backups(self) -> Collection[Mapping[str, str]]:
        pass

    @abstractmethod
    def create_integration_request(
            self,
            integration_manifest: Mapping[str, Any],
            engine_manifest: Mapping[str, Any],
            pin_code: str,
            ):
        pass

    @abstractmethod
    def approve_integration_request(self, request_id: UUID):
        pass

    @abstractmethod
    def get_ldap_settings(self) -> Mapping[str, Any]:
        pass


class WebSocketForbidden(websocket.WebSocketException):
    pass


class RecordingStartFailed(Exception):
    pass


class SettingsPreset:
    SECURITY = 'security'
