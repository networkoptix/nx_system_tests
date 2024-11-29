# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import MotionType
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_motion_type(distrib_url, one_vm_type, api_version, use_lexical, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    api = one_mediaserver.mediaserver().api
    [camera_ids] = api.add_test_cameras(offset=0, count=1)
    for motion_type in MotionType:
        api.set_motion_type_for_cameras([camera_ids.id], motion_type, use_lexical=use_lexical)
        camera = api.get_camera(camera_ids.id)
        assert camera.motion_type == motion_type
