# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import generate_mediaserver
from mediaserver_api import generate_mediaserver_user_attributes
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_generated_server(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    api = one_mediaserver.mediaserver().api
    api.setup_local_system()
    primary_1 = generate_mediaserver(index=1)
    api.add_generated_mediaserver(primary=primary_1)
    api.get_server(primary_1['id'])
    api.remove_server(primary_1['id'])
    assert api.get_server(primary_1['id']) is None
    primary_2 = generate_mediaserver(index=2)
    attributes = generate_mediaserver_user_attributes(primary_2)
    api.add_generated_mediaserver(primary=primary_2, attributes=attributes)
    api.get_server(primary_2['id'])
    api.remove_server(primary_2['id'])
    assert api.get_server(primary_2['id']) is None
