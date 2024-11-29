# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import argparse
import json
import logging
import os
import ssl
from collections.abc import Collection
from collections.abc import Mapping
from fnmatch import fnmatch
from pathlib import Path
from typing import Any
from typing import Optional
from typing import Sequence
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen

from _internal.service_registry import default_prerequisite_store
from cloud_api._cloud import CloudAccountFactory
from cloud_api._http import http_request
from cloud_api._push_notification import CloudPushNotificationsViewer
from _internal.push_notification_credentials import PUSH_NOTIFICATIONS_VIEWER_EMAIL
from _internal.push_notification_credentials import PUSH_NOTIFICATIONS_VIEWER_PASSWORD
from config import global_config
from infrastructure.secret_storage import PrivateKeyFileNotFound
from infrastructure.secret_storage import SecretNotFound
from infrastructure.secret_storage import get_secret

_logger = logging.getLogger(__name__)


class CloudHostArgparseAction(argparse.Action):
    dest = 'cloud_host'

    def __init__(
            self,
            *,
            option_strings: Sequence[str],
            dest: str,
            default: Optional[str] = None,
            **kwargs):
        [option, *aliases] = option_strings
        if aliases:
            raise ValueError(f"Aliases are not allowed: {aliases}")
        if not option.startswith('--'):
            raise ValueError(f"Must start with '--': {option}")
        if dest != option.lstrip('-').replace('-', '_'):
            raise ValueError(f"Custom dest is not allowed: {dest}")
        if kwargs:
            raise ValueError(f"Parameters are not allowed: {kwargs.keys()}")
        super().__init__(
            option_strings,
            self.dest,
            default=default or global_config.get('test_cloud_host') or None,
            required=not global_config.get('test_cloud_host'),
            type=self._cloud_host,
            )

    @staticmethod
    def _cloud_host(value: str) -> str:
        if urlparse(value).scheme:
            raise argparse.ArgumentTypeError("URLs are not supported")
        if not any(fnmatch(value, pattern) for pattern in _WHITELISTED_CLOUD_HOSTS):
            raise argparse.ArgumentTypeError(f"Cannot run tests on {value}")
        context = ssl.create_default_context(cafile=make_cloud_certs_path(value))
        url = f'https://{value}/api/ping'
        try:
            response = urlopen(url, timeout=10, context=context)
        except (URLError, ConnectionError) as e:
            raise argparse.ArgumentTypeError(f"{value!r} is not a valid cloud host; {e}")
        data = response.read()
        try:
            json.loads(data)
        except ValueError:
            raise argparse.ArgumentTypeError(
                f"{value!r} is not a valid cloud host; "
                f"failed to parse response from {url}")
        return value

    def __call__(self, parser, namespace, value, option_string=None):
        # The "dest" parameter is intentionally ignored.
        namespace.cloud_host = value


def _autotest_mail_credentials():
    email = os.environ.get('AUTOTEST_EMAIL')
    if email is not None:
        password = os.environ['AUTOTEST_EMAIL_PASSWORD']
        return email, password
    try:
        credentials_data = get_secret('autotest_mail_account')
    except (SecretNotFound, PrivateKeyFileNotFound) as e:
        _logger.debug(
            "Cannot get credentials for the autotest mail account from the storage: %s. "
            "Getting them from the environment variables / global_config",
            e)
        return 'ftcloudftcloud@networkoptix.com', os.environ.get('AUTOTEST_EMAIL_PASSWORD')
    else:
        credentials = json.loads(credentials_data.decode())
        email = credentials['email']
        password = credentials['password']
        return email, password


def make_cloud_certs_path(cloud_host: str) -> Path:
    if cloud_host.endswith('.nxcloud.us.networkoptix.dev'):
        # https://letsencrypt.org/docs/staging-environment/ + mozilla.pem
        return default_prerequisite_store.fetch('certs/with_staging.pem')
    # Taken from here: https://curl.se/docs/caextract.html
    return default_prerequisite_store.fetch('certs/mozilla.pem')


def make_cloud_account_factory(cloud_host):
    [autotest_email, autotest_email_password] = _autotest_mail_credentials()
    return CloudAccountFactory(
        cloud_host,
        autotest_email,
        autotest_email_password,
        cert_path=make_cloud_certs_path(cloud_host))


def make_push_notification_viewer(cloud_host):
    viewer = CloudPushNotificationsViewer(
        cloud_host,
        PUSH_NOTIFICATIONS_VIEWER_EMAIL,
        PUSH_NOTIFICATIONS_VIEWER_PASSWORD,
        )
    if not viewer.can_view_push_notifications():
        raise RuntimeError(
            f"No access to view push notifications. "
            f"Make sure that the user with the email {PUSH_NOTIFICATIONS_VIEWER_EMAIL} "
            f"on {cloud_host} has the following settings:\n"
            f"- has the 'Can view push notifications' permission;\n"
            f"- the 'is_staff' user attribute is set.")
    return viewer


# noinspection SpellCheckingInspection
_WHITELISTED_CLOUD_HOSTS = (
    '*.networkoptix.dev',  # Instances deployed in the K8s cluster
    'test.ft-cloud.hdw.mx',
    'cloud-test.hdw.mx',
    'stage.nxvms.com',
    'stage2.cloud.hdw.mx',
    'regress.cloud.hdw.mx',
    'dev3.cloud.hdw.mx',
    'qa.cloud.hdw.mx',
    'qa2.cloud.hdw.mx',
    'alicloud.nxcloud.nx-demo.com',
    'nxvms.com',
    )


def get_cms_settings(cloud_host: str) -> '_CMSData':
    response = http_request(
        method='GET',
        url=f'https://{cloud_host}/api/utils/settings',
        allow_redirects=True,
        ca_cert=str(make_cloud_certs_path(cloud_host)),
        )
    if response.status_code == 500:
        error_text = response.json['errorText']
        if 'SynchronousOnlyOperation' in error_text:
            raise RuntimeError(
                f"Failed to get CMS settings from {cloud_host}, "
                "probably because of the bug: SynchronousOnlyOperation in /api/utils/settings. "
                "See: https://networkoptix.atlassian.net/browse/CLOUD-14912")
        elif 'Flag: Enable For Developers pages' in error_text:
            raise RuntimeError(
                f"Failed to get CMS settings from {cloud_host}, probably because of the bug: "
                "'Enable For Developers pages' needs to have a value for field 'id'. "
                "See: https://networkoptix.atlassian.net/browse/CLOUD-15140")
        else:
            raise RuntimeError(f"Failed to get CMS settings from {cloud_host}: {error_text}")
    return _CMSData(response.json)


def _enable_flag(cloud_host: str, feature_name: str):
    response = http_request(
        method='POST',
        url=f'https://{cloud_host}/api/robot/set_flags',
        content={feature_name: True},
        ca_cert=str(make_cloud_certs_path(cloud_host)),
        ).json
    feature_status = response[feature_name]
    # If there is no such feature in the Cloud database,
    # the status of the feature in the response will be an empty list.
    if len(feature_status) == 0:
        _logger.warning(
            "Failed to enable %r feature. "
            "Looks like the Cloud has just been deployed and its DB isn't yet populated. "
            "Requesting data population and retrying",
            feature_name)
        _request_data_population(cloud_host)
        response = http_request(
            method='POST',
            url=f'https://{cloud_host}/api/robot/set_flags',
            content={feature_name: True},
            ca_cert=str(make_cloud_certs_path(cloud_host)),
            ).json
        feature_status = response[feature_name]
        if len(feature_status) == 0:
            raise RuntimeError(f"There is no {feature_name} feature in the Cloud database")
    [_, new_value] = feature_status
    if not isinstance(new_value, bool):
        raise RuntimeError(f"Unexpected response: {new_value}")
    if not new_value:
        raise RuntimeError(f"Failed to enable {feature_name} feature")


def _request_data_population(cloud_host: str):
    # According to the Cloud developers, this request forces
    # populating of the features in the Cloud database.
    http_request(
        method='GET',
        url=f'https://{cloud_host}/api/utils/settings',
        allow_redirects=True,
        ca_cert=str(make_cloud_certs_path(cloud_host)),
        )


def ensure_flags_enabled(cloud_host: str, flags: Collection[str]) -> None:
    cms_data = get_cms_settings(cloud_host)
    unsupported_flags = [flag for flag in flags if not cms_data.flag_is_enabled(flag)]
    if unsupported_flags:
        is_ft_cloud = cloud_host == global_config.get('test_cloud_host')
        is_pipeline_cloud = cloud_host.endswith('.networkoptix.dev')
        if is_ft_cloud or is_pipeline_cloud:
            for flag in unsupported_flags:
                _enable_flag(cloud_host, flag)
        else:
            raise RuntimeError(
                f"The following flags are disabled on the tested Cloud instance, "
                f"but are required for the test: "
                f"{', '.join(unsupported_flags)}")


def assert_channel_partners_supported(cloud_host: str) -> None:
    # This is an additional check in case all other checks pass by mistake.
    if cloud_host == 'nxvms.com':
        raise ChannelPartnersNotSupported(
            "Forbidden to run Channel Partners tests on the Production Cloud instance")
    response = http_request(
        method='GET',
        url=f'https://{cloud_host}/partners/internal/grant_access',
        ca_cert=str(make_cloud_certs_path(cloud_host)),
        )
    if response.status_code == 404:
        raise ChannelPartnersNotSupported(f"{cloud_host} doesn't support Channel Partners tests")
    if response.status_code != 200:
        raise RuntimeError(
            "Failed to check Channel Partners availability. "
            f"Unexpected response: {response.status_code} {response.json}")


class ChannelPartnersNotSupported(Exception):
    pass


class _CMSData:

    def __init__(self, raw_data: Mapping[str, Any]):
        self._raw_data = raw_data

    def get_cloud_name(self) -> str:
        return self._raw_data['cloudName']

    def get_company_name(self) -> str:
        return self._raw_data['companyName']

    def get_company_link(self) -> str:
        return self._raw_data['companyLink']

    def get_privacy_link(self) -> str:
        return self._raw_data['privacyLink']

    def get_support_link(self) -> str:
        return self._raw_data['supportLink']

    def flag_is_enabled(self, flag_name: str) -> bool:
        return bool(self._raw_data['featureFlags'][flag_name])
