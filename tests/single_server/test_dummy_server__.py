# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_dummy_server(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    api = one_mediaserver.mediaserver().api
    api.setup_local_system()
    dummy_server_id = api.add_dummy_mediaserver(1)
    api.get_server(dummy_server_id)
    new_name = 'new_dummy_server_name'
    api.rename_server(new_name, dummy_server_id)
    dummy_server = api.get_server(dummy_server_id)
    assert dummy_server.name == new_name
    api.remove_server(dummy_server_id)
    assert api.get_server(dummy_server_id) is None
