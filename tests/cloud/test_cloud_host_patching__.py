# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_set_cloud_host(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type)).mediaserver()
    new_cloud_host_1 = '1.example.com'
    mediaserver.stop(already_stopped_ok=True)
    time.sleep(2)  # TODO: Retry on 0xC0000043 in SmbPath.
    mediaserver.set_cloud_host(new_cloud_host_1)
    mediaserver.start()
    assert mediaserver.api.get_cloud_host() == new_cloud_host_1
    mediaserver.stop()
    time.sleep(2)  # TODO: Retry on 0xC0000043 in SmbPath.
    new_cloud_host_2 = '2.example.com'
    mediaserver.set_cloud_host(new_cloud_host_2)
    mediaserver.start()
    assert mediaserver.api.get_cloud_host() == new_cloud_host_2
