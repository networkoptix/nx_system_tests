# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import BadRequest
from mediaserver_api import Forbidden
from mediaserver_api import Permissions
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.infra import assert_raises

NONEXISTENT_USER_GROUP_GUID = '44e4161e-158e-2201-e000-000000000001'


def _test_missing_user_role(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    distrib = installer_supplier.distrib()
    distrib.assert_api_support(api_version, 'users')
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    # Try to create new user to non-existent group.
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    api = one_mediaserver.mediaserver().api
    initial_users = api.list_users()
    expected_exception = Forbidden if one_mediaserver.mediaserver().branch() == 'vms_5.0' else BadRequest
    with assert_raises(expected_exception):
        api.add_local_user('user1', 'irrelevant', group_id=NONEXISTENT_USER_GROUP_GUID)
    assert api.list_users() == initial_users
    # Try to link existing user to a missing group.
    group_id = api.add_user_group('test_group', [Permissions.NO_GLOBAL])
    user = api.add_local_user('user1', 'irrelevant', group_id=group_id)
    with assert_raises(expected_exception):
        api.set_user_group(user.id, group_id=NONEXISTENT_USER_GROUP_GUID)
    user = api.get_user(user.id)
    assert user.group_id == group_id
