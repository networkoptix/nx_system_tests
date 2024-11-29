# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from uuid import UUID

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_remove_child_resources(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver = one_mediaserver.mediaserver()
    api = one_mediaserver.api()
    server_id = api.add_dummy_mediaserver(1)
    assert server_id in api.list_system_mediaserver_ids()
    storage_id = api.add_dummy_smb_storage(1, parent_id=server_id)
    assert storage_id in [UUID(s['id']) for s in api.list_storages_info_brief()]
    camera_1, camera_2 = api.add_test_cameras(0, 2, parent_id=server_id)
    camera_1_id = camera_1.id
    camera_2_id = camera_2.id
    user = mediaserver.api.add_local_viewer('user1', 'irrelevant')
    camera_ids = [camera.id for camera in api.list_cameras()]
    assert camera_1_id in camera_ids
    assert camera_2_id in camera_ids
    for resource_id in [server_id, storage_id, camera_1_id, camera_2_id, user.id]:
        resource_param = {
            'resourceId': f'{resource_id}',
            'name': f'Resource_{resource_id}',
            'value': f'Value_{resource_id}',
            }
        api.http_post('ec2/setResourceParams', [resource_param])
        assert api.list_resource_params(resource_id)
    # Remove user
    api.remove_user(user.id)
    assert api.get_user(user.id) is None
    assert not api.list_resource_params(user.id)
    # Remove camera_2
    api.remove_resource(camera_2_id)
    assert camera_2_id not in [camera.id for camera in api.list_cameras()]
    assert not api.list_resource_params(camera_2_id)
    # Remove running_linux_server and check that all running_linux_server child resources have been removed
    api.remove_resource(server_id)
    assert storage_id not in [UUID(s['id']) for s in api.list_storages_info_brief()]
    assert camera_1_id not in [camera.id for camera in api.list_cameras()]
    for resource_id in [server_id, storage_id, camera_1_id]:
        assert not api.list_resource_params(resource_id)
