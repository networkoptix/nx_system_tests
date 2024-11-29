# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import Forbidden
from mediaserver_api import Permissions
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.infra import assert_raises


def _test_nonadministrator_cannot_get_metrics(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    distrib = installer_supplier.distrib()
    distrib.assert_api_support(api_version, 'users')
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver = one_mediaserver.mediaserver()
    group_id = mediaserver.api.add_user_group(
        'nonadmin_full_group',
        permissions=Permissions.NONADMIN_FULL_PRESET,
        )
    nonadmin = mediaserver.api.add_local_user('test_nonadmin_full', 'WellKnownPassword2', group_id=group_id)
    mediaserver_api_for_actor = mediaserver.api.as_user(nonadmin)
    with assert_raises(Forbidden):
        mediaserver_api_for_actor.get_metrics('system_info')
    with assert_raises(Forbidden):
        mediaserver_api_for_actor.list_metrics_alarms()
