# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

import requests
from requests.auth import HTTPDigestAuth

from ca import default_ca
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool

_logger = logging.getLogger(__name__)


def _test_http_header_server(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver = one_mediaserver.mediaserver()
    url = mediaserver.api.http_url('api/moduleInformationAuthenticated')
    credentials = mediaserver.api.get_credentials()
    valid_auth = HTTPDigestAuth(credentials.username, credentials.password)
    response = requests.get(url, auth=valid_auth, timeout=30, verify=default_ca().cert_path)
    _logger.debug('%r headers: %s', mediaserver, response.headers)
    assert response.status_code == 200
    assert 'Server' in response.headers.keys()
    invalid_auth = HTTPDigestAuth('invalid', 'invalid')
    response = requests.get(url, auth=invalid_auth, timeout=30, verify=default_ca().cert_path)
    _logger.debug('%r headers: %s', mediaserver, response.headers)
    assert response.status_code == 401
    assert 'WWW-Authenticate' in response.headers.keys()
    assert 'Server' not in response.headers.keys()
