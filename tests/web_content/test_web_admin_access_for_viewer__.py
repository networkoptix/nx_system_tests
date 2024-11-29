# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import Forbidden
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.infra import assert_raises
from tests.web_content._web_content_server import static_web_content_artifactory_url


def _test_web_admin_access_for_viewer(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    distrib = installer_supplier.distrib()
    static_web_content = installer_supplier.static_web_content()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    runner_address = one_mediaserver.os_access().source_address()
    url = exit_stack.enter_context(static_web_content_artifactory_url(static_web_content, runner_address, distrib))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver = one_mediaserver.mediaserver()
    live_viewer = mediaserver.api.add_local_live_viewer('live_viewer', 'WellKnownPassword2')
    api = mediaserver.api.as_user(live_viewer)
    # Make a request that requires authentication to automatically handle issues
    # such as disabled Basic and Digest authentication.
    assert api.credentials_work()
    api.get_static_web_content_info()
    with assert_raises(Forbidden):
        api.download_static_web_content(url)
    with assert_raises(Forbidden):
        api.upload_static_web_content(static_web_content.path.read_bytes())
    with assert_raises(Forbidden):
        api.reset_static_web_content()
