# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_api import EventType
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from tests.waiting import wait_for_truthy


def _test_analytics_storage_is_offline(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    camera_server = MultiPartJpegCameraServer()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    server = one_mediaserver.mediaserver()
    api = server.api
    os = server.os_access
    mount_point = os.mount_fake_disk('D', 50 * 1024 ** 3)
    server.enable_optional_plugins(['sample'])
    server.start()
    api.setup_local_system({'licenseServer': license_server.url()})
    server.allow_license_server_access(license_server.url())
    brand = server.api.get_brand()
    key = license_server.generate({'BRAND2': brand, 'QUANTITY2': 100})
    server.api.activate_license(key)
    [storage] = api.list_storages(str(mount_point))
    assert api.get_metadata_storage_id() == storage.id
    [camera] = add_cameras(server, camera_server)
    engine_collection = api.get_analytics_engine_collection()
    sample_engine = engine_collection.get_by_exact_name('Sample')
    with api.camera_recording(camera.id), camera_server.async_serve():
        api.enable_device_agent(sample_engine, camera.id)
        wait_for_truthy(
            api.list_analytics_objects_tracks,
            timeout_sec=30,
            description="some analytics tracks to be saved",
            )
        event_queue = api.event_queue()
        event_queue.skip_existing_events()
        os.dismount_fake_disk(mount_point)
        expected_events_attributes = {
            (EventType.STORAGE_FAILURE, 'metadataStorageOffline', 'diagnosticsAction'),
            (EventType.STORAGE_FAILURE, 'metadataStorageOffline', 'showPopupAction'),
            (EventType.STORAGE_FAILURE, 'storageIoError', 'diagnosticsAction'),
            (EventType.STORAGE_FAILURE, 'storageIoError', 'showPopupAction'),
            }
        actual_events_attributes = set()
        for _ in expected_events_attributes:
            event = event_queue.wait_for_next(timeout_sec=40)
            actual_events_attributes.add((event.event_type, event.reason_code, event.action_type))
        assert expected_events_attributes == actual_events_attributes
