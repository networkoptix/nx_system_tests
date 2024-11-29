# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import BadRequest
from mediaserver_api import Permissions
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.infra import assert_raises_with_message


def _test_cannot_create_users_with_empty_names(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    system_admin_api = one_mediaserver.mediaserver().api
    system_admin_api.setup_local_system()
    password = '12!StrongPassword34%'
    with assert_raises_with_message(BadRequest, 'Missing required parameter: name.'):
        system_admin_api.http_post(f'rest/{api_version}/users', {
            'password': password,
            'permissions': Permissions.NO_GLOBAL,
            })
    if system_admin_api.server_older_than('vms_6.0'):
        err_msg = "Won't save new user with empty name."
    else:
        err_msg = "Empty name is not allowed."
    with assert_raises_with_message(BadRequest, err_msg):
        system_admin_api.http_post(f'rest/{api_version}/users', {
            'name': '',
            'password': password,
            'permissions': Permissions.NO_GLOBAL,
            })
    with assert_raises_with_message(BadRequest, 'Invalid parameter `name`: null.'):
        system_admin_api.http_post(f'rest/{api_version}/users', {
            'name': None,
            'password': password,
            'permissions': Permissions.NO_GLOBAL,
            })
