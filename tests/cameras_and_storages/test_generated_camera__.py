# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import generate_camera
from mediaserver_api import generate_camera_user_attributes
from mediaserver_api import generate_resource_params
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_generated_camera(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    api = one_mediaserver.mediaserver().api
    primary_1 = generate_camera(index=1)
    api.add_generated_camera(primary=primary_1)
    assert api.get_camera(primary_1['id']) is not None
    api.remove_camera(primary_1['id'])
    assert api.get_camera(primary_1['id']) is None
    primary_2 = generate_camera(2, parent_id=str(api.get_server_id()))
    attributes = generate_camera_user_attributes(primary_2)
    params = generate_resource_params(primary_2, list_size=10)
    api.add_generated_camera(primary=primary_2, attributes=attributes, params=params)
    assert api.get_camera(primary_2['id']) is not None
    api.remove_camera(primary_2['id'])
    assert api.get_camera(primary_2['id']) is None
