# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from installation import ClassicInstallerSupplier
from mediaserver_api import Permissions
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.single_server.permissions.common import get_api_for_actor


def _test_cannot_activate(distrib_url, one_vm_type, api_version, actor, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver = one_mediaserver.mediaserver()
    license_key = license_server.generate({'BRAND2': mediaserver.api.get_brand()})
    mediaserver_api_for_actor = get_api_for_actor(mediaserver.api, actor)
    mediaserver.allow_license_server_access(license_server.url())
    mediaserver.api.set_license_server(license_server.url())
    try:
        mediaserver_api_for_actor.activate_license(license_key)
    except Exception as e:
        if api_version == 'v0':
            error_string = "Can't activate license because user has not enough access rights"
        else:
            credentials = mediaserver_api_for_actor.get_credentials()
            if mediaserver.api.server_older_than('vms_6.0'):
                error_string = (
                    f"User {credentials.username} "
                    f"with Default permissions "
                    f"is asking for {Permissions.ADMIN} permissions and fails")
            else:
                error_string = (
                    f"User {credentials.username} "
                    f"with Default permissions "
                    f"has no {Permissions.ADMIN} permissions")
        assert error_string in str(e)
    else:
        raise Exception("Did not raise")
