# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import math
from datetime import datetime
from datetime import timedelta
from datetime import timezone

import requests
from requests.auth import HTTPDigestAuth

from ca import default_ca
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.waiting import wait_for_truthy

_logger = logging.getLogger(__name__)


def _test_auth_with_time_changed(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver = one_mediaserver.mediaserver()
    timeless_server = mediaserver
    timeless_server.api.become_primary_time_server()
    assert timeless_server.api.is_primary_time_server()
    url = timeless_server.api.http_url('api/moduleInformationAuthenticated')

    timeless_server.os_access.set_datetime(datetime.now(timezone.utc))
    wait_for_truthy(
        lambda: math.isclose(_offset_from_local(timeless_server.api), 0, abs_tol=1),
        description="time on {} is close to now".format(timeless_server))

    shift = timedelta(days=3)

    credentials = timeless_server.api.get_credentials()
    response = requests.get(
        url,
        auth=HTTPDigestAuth(credentials.username, credentials.password),
        verify=default_ca().cert_path,
        )
    authorization_header_value = response.request.headers['Authorization']
    _logger.info(authorization_header_value)
    response = requests.get(
        url,
        headers={'Authorization': authorization_header_value},
        verify=default_ca().cert_path,
        )
    response.raise_for_status()

    timeless_server.os_access.set_datetime(datetime.now(timezone.utc) + shift)
    wait_for_truthy(
        lambda: math.isclose(_offset_from_local(timeless_server.api), shift.total_seconds(), abs_tol=1),
        description="time on {} is close to now + {}".format(timeless_server, shift))

    response = requests.get(
        url,
        headers={'Authorization': authorization_header_value},
        verify=default_ca().cert_path,
        )
    assert response.status_code != 401
    response.raise_for_status()


def _offset_from_local(api):
    return api.get_datetime().timestamp() - datetime.now(timezone.utc).timestamp()
