# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import OldSessionToken
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.infra import assert_raises
from tests.web_content._web_content_server import static_web_content_artifactory_url
from tests.web_content.common import make_session_old


def _test_reset_static_web_content(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    distrib = installer_supplier.distrib()
    static_web_content = installer_supplier.static_web_content()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    runner_address = one_mediaserver.os_access().source_address()
    url = exit_stack.enter_context(static_web_content_artifactory_url(static_web_content, runner_address, distrib))
    server = one_mediaserver.mediaserver()
    api = server.api
    server.start()
    api.setup_local_system()
    static_web_content_info = api.download_static_web_content(url)
    assert static_web_content_info['source'] == url
    api.reset_static_web_content()
    static_web_content_info = api.get_static_web_content_info()
    assert static_web_content_info['source'] == 'builtin'
    make_session_old(server)
    api.disable_auth_refresh()
    with assert_raises(OldSessionToken):
        api.reset_static_web_content()
