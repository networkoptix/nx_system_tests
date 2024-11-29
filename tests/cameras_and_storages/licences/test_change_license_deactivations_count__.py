# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.waiting import wait_for_equal


def _test_change_license_deactivations_count(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.start()
    mediaserver.api.setup_local_system({'licenseServer': license_server.url()})
    grant_license(mediaserver, license_server)
    [license_before] = mediaserver.api.list_licenses()
    assert license_before.deactivations == 0
    license_server.deactivate(license_before.key)
    license_server.activate(license_before.key, license_before.hwid)
    mediaserver.api.restart()
    wait_for_equal(
        _get_license_deactivation_count,
        expected=1,
        args=(mediaserver.api,),
        timeout_sec=15,
        )


def _get_license_deactivation_count(api):
    [vms_license] = api.list_licenses()
    return vms_license.deactivations
