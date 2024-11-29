# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.cameras_and_storages.licences.common import key_is_absent
from tests.waiting import wait_for_truthy


def _test_license_check_interval(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.start()
    mediaserver.api.setup_local_system({'licenseServer': license_server.url()})
    grant_license(mediaserver, license_server)
    ping_interval_sec = 30
    mediaserver.update_ini('nx_vms_server', {'licenseServerPingInterval': ping_interval_sec})
    mediaserver.api.restart()
    [license] = mediaserver.api.list_licenses()
    key = license.key
    license_server.deactivate(key)
    timeout_sec = ping_interval_sec + 5  # Extra 5 seconds for reliability
    wait_for_truthy(key_is_absent, args=(mediaserver, key), timeout_sec=timeout_sec)