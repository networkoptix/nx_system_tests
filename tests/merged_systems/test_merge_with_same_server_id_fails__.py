# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from uuid import uuid4

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import MergeDuplicateMediaserverFound
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.infra import assert_raises


def _test_cannot_merge_servers_with_same_id(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    common_server_id = "{{{}}}".format(uuid4())
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    first = two_mediaservers.first.installation()
    second = two_mediaservers.second.installation()

    for server in first, second:
        server.update_conf({'serverGuid': common_server_id, 'guidIsHWID': 'no'})
        server.start()
        server.api.setup_local_system()

    with assert_raises(MergeDuplicateMediaserverFound):
        merge_systems(first, second, take_remote_settings=False)
