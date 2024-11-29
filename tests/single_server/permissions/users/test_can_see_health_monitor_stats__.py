# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_can_see_health_monitor_stats(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    distrib = installer_supplier.distrib()
    distrib.assert_api_support(api_version, 'users')
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    system_admin_api = one_mediaserver.mediaserver().api
    system_admin_api.setup_local_system()

    admin = system_admin_api.add_local_admin('test_admin', 'WellKnownPassword2')
    admin_api = system_admin_api.as_user(admin)
    viewer = system_admin_api.add_local_viewer('test_viewer', 'WellKnownPassword2')
    viewer_api = system_admin_api.as_user(viewer)
    live_viewer = system_admin_api.add_local_live_viewer('test_live_viewer', 'WellKnownPassword2')
    live_viewer_api = system_admin_api.as_user(live_viewer)
    adv_viewer = system_admin_api.add_local_advanced_viewer('test_advanced_viewer', 'WellKnownPassword2')
    adv_viewer_api = system_admin_api.as_user(adv_viewer)

    admin_api.get_server_statistics()
    viewer_api.get_server_statistics()
    live_viewer_api.get_server_statistics()
    adv_viewer_api.get_server_statistics()
