# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_shared_local_session(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    two_mediaservers.start()
    two_mediaservers.setup_system()
    two_mediaservers.merge()
    one = two_mediaservers.first.installation()
    two = two_mediaservers.second.installation()
    credentials = one.api.get_credentials()
    assert credentials.auth_type == 'bearer'
    assert credentials.token is not None
    server_2_api = two.api.with_auth_handler(one.api.get_auth_handler())
    assert credentials == server_2_api.get_credentials()
    assert one.api.credentials_work()
    session_token = credentials.token
    credentials = server_2_api.get_credentials()
    assert credentials.auth_type == 'bearer'
    assert credentials.token == session_token
    assert server_2_api.credentials_work()
    one.stop()
    # Wait before checking that the session from the first server is working if the server is down.
    time.sleep(5)
    credentials = server_2_api.get_credentials()
    assert credentials.auth_type == 'bearer'
    assert credentials.token == session_token
    assert server_2_api.credentials_work()
    one.start()
    credentials = one.api.get_credentials()
    assert credentials.auth_type == 'bearer'
    assert credentials.token == session_token
    assert one.api.credentials_work()
    credentials = server_2_api.get_credentials()
    assert credentials.auth_type == 'bearer'
    assert credentials.token == session_token
    assert server_2_api.credentials_work()
    server_2_api.restart()
    credentials = one.api.get_credentials()
    assert credentials.auth_type == 'bearer'
    assert credentials.token == session_token
    assert one.api.credentials_work()
    credentials = server_2_api.get_credentials()
    assert credentials.auth_type == 'bearer'
    assert credentials.token == session_token
    assert server_2_api.credentials_work()
