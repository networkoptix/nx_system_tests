# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import public_ip_check_addresses
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.waiting import wait_for_truthy

_logger = logging.getLogger(__name__)


def _test_setup_cloud_system_enable_internet_after_start(cloud_host, distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    cloud_account_factory = make_cloud_account_factory(cloud_host)
    cloud_account = cloud_account_factory.create_account()
    customization_name = installer_supplier.distrib().customization().customization_name
    cloud_account.set_user_customization(customization_name)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    mediaserver = one_mediaserver.mediaserver()
    # Set the public IP discovery interval to 500 ms to speed up the test.
    mediaserver.update_ini('nx_vms_server', {'publicIpDiscoveryIntervalMs': 500})
    mediaserver.set_cloud_host(cloud_host)
    mediaserver.os_access.cache_dns_in_etc_hosts([cloud_host, *public_ip_check_addresses])
    mediaserver.start()
    mediaserver.allow_access_to_cloud(cloud_host)
    wait_for_truthy(mediaserver.api.has_public_ip)
    mediaserver.api.setup_cloud_system(cloud_account)
