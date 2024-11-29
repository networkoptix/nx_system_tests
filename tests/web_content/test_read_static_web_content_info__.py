# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_read_static_web_content_info(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    static_web_content = installer_supplier.static_web_content()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    server = one_mediaserver.mediaserver()
    api = one_mediaserver.api()
    server.start()
    api.setup_local_system()
    static_web_content_info = api.get_static_web_content_info()
    assert static_web_content_info['details'] == static_web_content.details
    assert static_web_content_info['source'] == 'builtin'
    api.disable_auth_refresh()
    api.get_static_web_content_info()
