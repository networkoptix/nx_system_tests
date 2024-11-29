# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import MergeDuplicateMediaserverFound
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.infra import assert_raises


def _test_cannot_merge_systems_with_same_server(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    two_mediaservers.start()
    two_mediaservers.setup_system()
    two_mediaservers.merge()
    one = two_mediaservers.first.installation()
    two = two_mediaservers.second.installation()

    two.api.restore_state()
    two.api.setup_local_system()

    for take_remote_settings in (False, True):
        with assert_raises(MergeDuplicateMediaserverFound):
            merge_systems(one, two, take_remote_settings=take_remote_settings)

    one.api.remove_server(two.api.get_server_id())
    merge_systems(one, two, take_remote_settings=False)
