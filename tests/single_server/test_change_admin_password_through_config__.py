# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_change_admin_password_through_config(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.stop()
    new_password = 'admin1234'
    mediaserver.update_conf({'appserverPassword': new_password})
    mediaserver.start()
    api_with_old_credentials = mediaserver.api
    credentials = api_with_old_credentials.get_credentials()
    api_with_new_credentials = mediaserver.api.with_credentials(
        credentials.username,
        new_password,
        )
    # VMS-29359: After admin password reset, its authorization methods are also reset.
    assert mediaserver.api.basic_and_digest_auth_disabled()
    # Since test uses basic and digest authentications, they must be enabled.
    # It requires an API object with the correct credentials.
    api_with_new_credentials.enable_basic_and_digest_auth_for_admin()
    assert not api_with_old_credentials.credentials_work()
    assert api_with_new_credentials.credentials_work()
