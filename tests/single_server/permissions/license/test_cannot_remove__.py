# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from installation import ClassicInstallerSupplier
from mediaserver_api import Forbidden
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.infra import assert_raises
from tests.single_server.permissions.common import get_api_for_actor


def _test_cannot_remove(distrib_url, one_vm_type, api_version, actor, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver = one_mediaserver.mediaserver()
    license_key = license_server.generate({'BRAND2': mediaserver.api.get_brand()})
    # The API for remove_license method doesn't check license block is valid,
    # but it checks license key is exists. Fake license block enough here
    # to check user permissions.
    mediaserver.api.add_license(license_key, license_block='Test License')
    mediaserver_api_for_actor = get_api_for_actor(mediaserver.api, actor)
    with assert_raises(Forbidden):
        mediaserver_api_for_actor.remove_license(license_key)
