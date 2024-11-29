# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import Forbidden
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.infra import assert_raises


def _test_videowall_permissions(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    distrib = installer_supplier.distrib()
    distrib.assert_api_support(api_version, 'users')
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    system_admin_api = one_mediaserver.mediaserver().api
    system_admin_api.setup_local_system()

    system_admin_videowall_id = system_admin_api.add_videowall('videowall_by_system_admin')
    system_admin_api.dummy_control_videowall(system_admin_videowall_id)
    system_admin_api.remove_videowall(system_admin_videowall_id)
    system_admin_videowall_id = system_admin_api.add_videowall('videowall_by_system_admin')
    system_admin_api.remove_resource(system_admin_videowall_id)

    admin = system_admin_api.add_local_admin('test_admin', 'WellKnownPassword2')
    admin_api = system_admin_api.as_user(admin)
    admin_videowall_id = admin_api.add_videowall('videowall_by_admin')
    admin_api.dummy_control_videowall(admin_videowall_id)
    admin_api.remove_videowall(admin_videowall_id)
    admin_videowall_id = admin_api.add_videowall('videowall_by_admin')
    admin_api.remove_resource(admin_videowall_id)

    system_admin_videowall_id = system_admin_api.add_videowall('videowall_by_system_admin')

    viewer = system_admin_api.add_local_viewer('test_viewer', 'WellKnownPassword2')
    viewer_api = system_admin_api.as_user(viewer)
    with assert_raises(Forbidden):
        viewer_api.add_videowall('videowall_by_viewer')
    with assert_raises(Forbidden):
        viewer_api.dummy_control_videowall(system_admin_videowall_id)
    with assert_raises(Forbidden):
        viewer_api.remove_videowall(system_admin_videowall_id)
    with assert_raises(Forbidden):
        viewer_api.remove_resource(system_admin_videowall_id)

    live_viewer = system_admin_api.add_local_live_viewer('test_live_viewer', 'WellKnownPassword2')
    live_viewer_api = system_admin_api.as_user(live_viewer)
    with assert_raises(Forbidden):
        live_viewer_api.add_videowall('videowall_by_live_viewer')
    with assert_raises(Forbidden):
        live_viewer_api.dummy_control_videowall(system_admin_videowall_id)
    with assert_raises(Forbidden):
        live_viewer_api.remove_videowall(system_admin_videowall_id)
    with assert_raises(Forbidden):
        live_viewer_api.remove_resource(system_admin_videowall_id)

    advanced_viewer = system_admin_api.add_local_advanced_viewer('test_advanced_viewer', 'WellKnownPassword2')
    advanced_viewer_api = system_admin_api.as_user(advanced_viewer)
    with assert_raises(Forbidden):
        advanced_viewer_api.add_videowall('videowall_by_advanced_viewer')
    with assert_raises(Forbidden):
        advanced_viewer_api.dummy_control_videowall(system_admin_videowall_id)
    with assert_raises(Forbidden):
        advanced_viewer_api.remove_videowall(system_admin_videowall_id)
    with assert_raises(Forbidden):
        advanced_viewer_api.remove_resource(system_admin_videowall_id)
