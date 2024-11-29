# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_api import EventType
from mediaserver_api import MediaserverApiHttpError
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from tests.waiting import wait_for_truthy

_logger = logging.getLogger(__name__)


def _test_analytics_storage_out_of_space(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    camera_server = MultiPartJpegCameraServer()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    mediaserver = one_mediaserver.mediaserver()
    api = one_mediaserver.api()
    os = mediaserver.os_access
    disk_size_mb = 15 * 1024
    one_mediaserver.hardware().add_disk('sata', disk_size_mb)
    min_metadata_storage_free_space_mb = disk_size_mb // 2
    mediaserver.update_ini(
        'nx_vms_server', {'minMetadataStorageFreeSpace': min_metadata_storage_free_space_mb})
    small_disk_mount_point = os.mount_disk('S')
    mediaserver.enable_optional_plugins(['sample'])
    mediaserver.start()
    api.setup_local_system({'licenseServer': license_server.url()})
    mediaserver.allow_license_server_access(license_server.url())
    brand = mediaserver.api.get_brand()
    key = license_server.generate({'BRAND2': brand})
    mediaserver.api.activate_license(key)
    [small_storage] = api.list_storages(str(small_disk_mount_point))
    wait_for_truthy(
        lambda: all(s.is_enabled for s in api.list_storages()),
        timeout_sec=30,
        description="all storages become online",
        )
    # VMS-34784: Workaround for v5.0 (issue was fixed in 5.1+)
    api.allocate_storage_for_analytics(small_storage.id)
    api.disable_storage(small_storage.id)
    assert api.get_metadata_storage_id() == small_storage.id
    one_mediaserver.hardware().add_disk('sata', 2 * disk_size_mb)
    os.mount_disk('L')
    mediaserver.stop()
    mediaserver.start()
    [camera] = add_cameras(mediaserver, camera_server)
    engine_collection = api.get_analytics_engine_collection()
    engine = engine_collection.get_by_exact_name('Sample')
    with api.camera_recording(camera.id), camera_server.async_serve():
        api.enable_device_agent(engine, camera.id)
        old_objects = wait_for_truthy(
            api.list_analytics_objects_tracks,
            timeout_sec=60,
            description="some analytics tracks to be saved",
            )
        # VMS-27833: Reserve some space to avoid database corruption
        # Value should be smaller than min_metadata_storage_free_space_mb during test running
        reserved_space_mb = min_metadata_storage_free_space_mb // 2
        os.create_file(
            small_disk_mount_point / 'big_file.bin',
            # Making file bigger results in out of space error
            file_size_b=(disk_size_mb - reserved_space_mb) * 1024 ** 2,
            )
        event_queue = api.event_queue()
        event_queue.skip_existing_events()
        try:
            wait_for_truthy(
                lambda: all(o not in api.list_analytics_objects_tracks() for o in old_objects),
                timeout_sec=60,
                description="old analytics tracks are overwritten by newer ones",
                )
        except MediaserverApiHttpError as e:
            if e.http_status == 500:
                raise RuntimeError(
                    "API call /ec2/getAnalyticsObjects ended with HTTP status 500. "
                    "This is likely caused by database corruption, "
                    "which is likely caused by a lack of free space on the disk. "
                    "Try to avoid that by reserving some more space "
                    "(currently, 1500 MB), check out VMS-27833.")
            raise
        expected_events_attributes = {
            (EventType.STORAGE_FAILURE, 'metadataStorageFull', 'showPopupAction'),
            (EventType.STORAGE_FAILURE, 'metadataStorageFull', 'diagnosticsAction'),
            }
        actual_events_actions = set()
        for _ in expected_events_attributes:
            event = event_queue.wait_for_next(timeout_sec=60)
            actual_events_actions.add((event.event_type, event.reason_code, event.action_type))
        assert expected_events_attributes == actual_events_actions
