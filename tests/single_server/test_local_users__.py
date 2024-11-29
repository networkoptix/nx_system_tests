# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import re

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import BadRequest
from mediaserver_api import Forbidden
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.infra import assert_raises


def _test_local_users(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    distrib = installer_supplier.distrib()
    distrib.assert_specific_feature('minimal_internal_api', 2)
    api = one_mediaserver.api()
    known_users = api.list_users()
    local_user_password = 'irrelevant'
    local_user = api.add_local_user('local_user_1', local_user_password)
    local_user = api.get_user(local_user.id)
    assert local_user is not None, f"Local user {local_user.id} not found."
    assert api.with_credentials(local_user.name, local_user_password).credentials_work()
    assert not local_user.is_cloud
    assert local_user.is_enabled
    generated_user_data = api.add_generated_user(idx=1)
    generated_user = api.get_user(generated_user_data.id)
    assert generated_user is not None, f"Generated user {generated_user_data.id} not found."
    all_users = api.list_users()
    assert local_user in all_users
    assert generated_user in all_users
    new_local_user_password = 'new_password'
    api.set_user_password(local_user.id, new_local_user_password)
    assert api.with_credentials(local_user.name, new_local_user_password).credentials_work()
    api.disable_user(local_user.id)
    local_user = api.get_user(local_user.id)
    assert not local_user.is_enabled
    new_name = 'New_name'
    new_email = 'new.email@example.com'
    # User name cannot be changed without specifying user password (VMS-22103, VMS-23474)
    password = generated_user_data.password
    if api_version == 'v0':
        with assert_raises(Forbidden):
            api.rename_user(generated_user.id, new_name)
    elif api_version == 'v1':
        # In the new API, it only works if digest authentication is enabled for the user
        api.enable_basic_and_digest_auth_for_user(generated_user.id, password=password)
        try:
            api.rename_user(generated_user.id, new_name)
        except BadRequest as e:
            message_template = r"Not possible to \w+ name with HTTP digest without a password"
            assert re.match(message_template, e.vms_error_string)
        else:
            raise Exception("Did not raise")
    api.set_user_credentials(generated_user.id, name=new_name, password=password)
    api.set_user_email(generated_user.id, new_email)
    generated_user = api.get_user(generated_user.id)
    assert generated_user.name == new_name
    assert generated_user.email == new_email
    api.remove_user(local_user.id)
    assert api.get_user(local_user.id) is None
    api.remove_user(generated_user.id)
    assert api.get_user(generated_user.id) is None
    assert api.list_users() == known_users
