# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import math
import time

from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import public_ip_check_addresses
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_session_lifetime(cloud_host, distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    cloud_account_factory = make_cloud_account_factory(cloud_host)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    stand = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    mediaserver = stand.mediaserver()
    mediaserver.os_access.cache_dns_in_etc_hosts([cloud_host, *public_ip_check_addresses])
    mediaserver.allow_access_to_cloud(cloud_host)
    mediaserver.set_cloud_host(cloud_host)
    mediaserver.start()
    cloud_account = cloud_account_factory.create_account()
    session_lifetime_sec = 40
    cloud_account.set_session_lifetime(lifetime_sec=session_lifetime_sec)
    mediaserver.api.setup_cloud_system(cloud_account)
    credentials = mediaserver.api.get_credentials()
    session_info = mediaserver.api.get_session_info(credentials.token)
    assert math.isclose(
        session_info.age_sec + session_info.expires_in_sec,
        session_lifetime_sec,
        abs_tol=1,
        )
    mediaserver.api.disable_auth_refresh()
    assert mediaserver.api.credentials_work()
    mediaserver.block_access_to_cloud(cloud_host)
    # Wait before checking that the session works without access to the cloud.
    time.sleep(5)
    assert mediaserver.api.credentials_work()
    mediaserver.os_access.cache_dns_in_etc_hosts([cloud_host, *public_ip_check_addresses])
    mediaserver.allow_access_to_cloud(cloud_host)
    assert mediaserver.api.credentials_work()
    session_info = mediaserver.api.get_session_info(credentials.token)
    should_remain_before_expiration_sec = 5
    assert session_info.expires_in_sec > should_remain_before_expiration_sec
    time.sleep(session_info.expires_in_sec - should_remain_before_expiration_sec)
    assert mediaserver.api.credentials_work()
    time.sleep(should_remain_before_expiration_sec + 2)  # Plus a few extra seconds for reliability
    assert not mediaserver.api.credentials_work()
