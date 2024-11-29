# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import JPEGSequence
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from vm.default_vm_pool import public_default_vm_pool
from vm.default_vm_pool import vm_types


def _test_disk_usage_statistics(
        distrib_url,
        one_vm_type,
        first_disk_size_mb,
        second_disk_size_mb,
        statistics_ratio_tolerance,
        api_version,
        exit_stack,
        ):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    artifacts_dir = get_run_dir()
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    vm_pool = public_default_vm_pool(artifacts_dir)
    one_vm = exit_stack.enter_context(vm_pool.clean_vm(vm_types[one_vm_type]))
    one_vm.ensure_started(artifacts_dir)
    exit_stack.enter_context(one_vm.os_access.prepared_one_shot_vm(artifacts_dir))
    video_source = JPEGSequence(frame_size=(2048, 1024))
    camera_server = MultiPartJpegCameraServer(video_source=video_source)
    # FT cannot make noticeable load for HDD using camera recording.
    # CPU is reaching it's limit first, and by that time HDD is loaded for about 5%.
    # With low disk load HDD statistics is very, very volatile value.
    # Note, that if disk size difference is more than 1:2, than smaller disk usage is
    # close to zero most of the time, and it will affect test result. For better accuracy only
    # 1:1 and 1:2 disks are used in test.
    vm = one_vm.vm_control
    os = one_vm.os_access
    vm.add_disk('sata', first_disk_size_mb)
    first_mount_path = os.mount_disk('L')
    vm.add_disk('sata', second_disk_size_mb)
    second_mount_path = os.mount_disk('M')
    mounted_disks = os.list_mounted_disks()
    first_disk_name = mounted_disks[first_mount_path]
    second_disk_name = mounted_disks[second_mount_path]
    with pool.mediaserver_allocation(os) as mediaserver:
        mediaserver.allow_license_server_access(license_server.url())
        mediaserver.update_conf({'mediaFileDuration': 1})
        mediaserver.start()
        api = mediaserver.api
        api.setup_local_system({'licenseServer': license_server.url()})
        [default_storage] = api.list_storages(str(mediaserver.default_archive_dir))
        api.disable_storage(default_storage.id)
        camera_count = 20
        brand = mediaserver.api.get_brand()
        key = license_server.generate({'BRAND2': brand, 'QUANTITY2': camera_count})
        mediaserver.api.activate_license(key)
        cameras = add_cameras(mediaserver, camera_server, indices=range(camera_count))
        with camera_server.async_serve():
            api.start_recording(*[camera.id for camera in cameras])
            time.sleep(10)  # Serve for some time to exclude zero disk usage from statistics.
            first_disks_usage_list = []
            second_disks_usage_list = []
            statistics_period_sec = int(api.get_server_statistics()['updatePeriod']) / 1000
            started_at = time.monotonic()
            while time.monotonic() - started_at < 240:
                current_disk_stats = api.get_hdd_statistics()
                first_disks_usage_list.append(current_disk_stats[first_disk_name])
                second_disks_usage_list.append(current_disk_stats[second_disk_name])
                time.sleep(statistics_period_sec)
        actual_usage_ratio = sum(first_disks_usage_list) / sum(second_disks_usage_list)
        [low_threshold, high_threshold] = statistics_ratio_tolerance
        assert low_threshold <= actual_usage_ratio <= high_threshold
