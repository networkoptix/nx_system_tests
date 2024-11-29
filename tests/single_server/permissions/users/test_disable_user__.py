# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_disable_user(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    system_admin_api = one_mediaserver.mediaserver().api
    system_admin_api.setup_local_system()

    [username, password] = 'testuser', 'p2ss234'
    test_user = system_admin_api.add_local_admin(username, password)
    if api_version != 'v0':
        system_admin_api.enable_basic_and_digest_auth_for_user(test_user.id, password=password)
    test_user_api_digest = system_admin_api.with_digest_auth(username, password)
    test_user_api_basic = system_admin_api.with_basic_auth(username, password)
    assert test_user_api_digest.credentials_work()
    assert test_user_api_basic.credentials_work()

    system_admin_api.disable_user(test_user.id)
    assert not test_user_api_digest.credentials_work()
    assert not test_user_api_basic.credentials_work()
