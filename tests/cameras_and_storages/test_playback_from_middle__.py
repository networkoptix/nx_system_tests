# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import math
from datetime import timedelta

from _internal.service_registry import default_prerequisite_store
from ca import default_ca
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import H264RtspCameraServer
from doubles.video.ffprobe import SampleMediaFile
from doubles.video.hls import get_hls_start_datetime
from installation import ClassicInstallerSupplier
from mediaserver_api import TimePeriod
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.software_camera_scenarios import record_from_cameras


def _test_playback_from_middle(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.start()
    mediaserver.api.setup_local_system({'licenseServer': license_server.url()})
    grant_license(mediaserver, license_server)
    media_sample = SampleMediaFile(default_prerequisite_store.fetch('test-cam/sample_gop_15.264'))
    camera_server = H264RtspCameraServer(
        source_video_file=media_sample.path,
        fps=media_sample.fps,
        )
    [camera] = add_cameras(mediaserver, camera_server)
    [period] = record_from_cameras(
        mediaserver.api,
        [camera],
        camera_server,
        duration_sec=20,
        )
    # Note that half duration of record must be at least 5 seconds,
    # because mediaserver cannot stream records less than 5 seconds long.
    half_duration = timedelta(seconds=period.duration_sec / 2)
    period_from_middle = TimePeriod.from_datetime(period.start + half_duration)
    middle_stream_url = mediaserver.api.hls_url(camera.id, period_from_middle)
    stream_start = get_hls_start_datetime(middle_stream_url, default_ca())
    assert math.isclose(stream_start.timestamp(), period_from_middle.start.timestamp(), abs_tol=1)
