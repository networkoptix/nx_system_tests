# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys
import time

from cloud_api.cloud import make_cloud_account_factory
from cloud_api.cloud import make_cloud_certs_path
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import public_ip_check_addresses
from mediaserver_api import MediaserverApi
from mediaserver_api import MediaserverApiConnectionError
from mediaserver_api import MediaserverApiHttpError
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from runner.ft_test import run_ft_test
from tests.base_test import CloudTest
from tests.base_test import VMSTest


class test_can_request_via_relay(VMSTest, CloudTest):
    """Test can request via relay.

    See: https://networkoptix.atlassian.net/browse/FT-2017
    Selection-Tag: no_testrail
    Selection-Tag: cloud_portal_gitlab
    Selection-Tag: cloud_portal_smoke
    """

    def _run(self, args, exit_stack):
        installer_supplier = ClassicInstallerSupplier(args.distrib_url)
        cloud_host = args.cloud_host
        cloud_account_factory = make_cloud_account_factory(cloud_host)
        cloud_account = exit_stack.enter_context(cloud_account_factory.temp_account())
        customization_name = installer_supplier.distrib().customization().customization_name
        cloud_account.set_user_customization(customization_name)
        pool = FTMachinePool(installer_supplier, get_run_dir(), 'v2')
        stand = exit_stack.enter_context(pool.one_mediaserver('ubuntu22'))
        mediaserver = stand.mediaserver()
        services_hosts = cloud_account.get_services_hosts()
        mediaserver.os_access.cache_dns_in_etc_hosts([cloud_host, *services_hosts, *public_ip_check_addresses])
        mediaserver.allow_access_to_cloud(cloud_host, services_hosts=services_hosts)
        mediaserver.set_cloud_host(cloud_host)
        mediaserver.start()
        mediaserver.api.setup_cloud_system(cloud_account)
        cloud_system_id = mediaserver.api.get_cloud_system_id()
        cloud_ca_cert = make_cloud_certs_path(cloud_host)
        [relay_host, *_others] = services_hosts
        relay_api = mediaserver.api.as_relay(relay_host, cloud_system_id, cloud_ca_cert)
        _wait_for_relay(relay_api)


def _wait_for_relay(relay_api: MediaserverApi):
    timeout_sec = 5
    started_at = time.monotonic()
    while True:
        try:
            relay_api.get_system_settings()
        except (MediaserverApiConnectionError, MediaserverApiHttpError):
            pass
        else:
            break
        if time.monotonic() - started_at > timeout_sec:
            raise RuntimeError(f"Relay isn't available in {timeout_sec} second(s)")
        time.sleep(1)


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [
        test_can_request_via_relay(),
        ]))
