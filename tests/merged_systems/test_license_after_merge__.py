# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.waiting import wait_for_equal


def _test_license_after_merge(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    explicitly_licensed_server = two_mediaservers.first.installation()
    implicitly_licensed_server = two_mediaservers.second.installation()
    explicitly_licensed_server.start()
    explicitly_licensed_server.api.setup_local_system({'licenseServer': license_server.url()})
    explicitly_licensed_server.allow_license_server_access(license_server.url())
    brand = explicitly_licensed_server.api.get_brand()
    key = license_server.generate({'BRAND2': brand})
    explicitly_licensed_server.api.activate_license(key)
    implicitly_licensed_server.start()
    implicitly_licensed_server.api.setup_local_system()
    merge_systems(implicitly_licensed_server, explicitly_licensed_server, take_remote_settings=True)
    original_licenses = explicitly_licensed_server.api.list_licenses()
    wait_for_equal(implicitly_licensed_server.api.list_licenses, original_licenses)
