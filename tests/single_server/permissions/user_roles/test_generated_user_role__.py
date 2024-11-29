# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import Permissions
from mediaserver_api import UserGroupNotFound
from mediaserver_api import generate_group
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.infra import assert_raises


def _test_generated_user_role(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    distrib = installer_supplier.distrib()
    distrib.assert_api_support(api_version, 'users')
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    api = one_mediaserver.mediaserver().api
    generated_group_data = generate_group(index=1, permissions=Permissions.ACCESS_ALL_MEDIA)
    group_id = api.add_generated_user_group(generated_group_data)
    group = api.get_user_group(group_id)
    assert group.name == generated_group_data['name']
    assert group.permissions == set(generated_group_data['permissions'].split('|'))
    api.remove_user_group(group.id)
    with assert_raises(UserGroupNotFound):
        api.get_user_group(group_id)
