# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from functools import partial

from directories import get_run_dir
from doubles.software_cameras import MjpegRtspCameraServer
from doubles.software_cameras import MultiPartJpegCameraServer
from doubles.video.multipart_reader import ConnectionClosed
from doubles.video.multipart_reader import get_frames
from doubles.video.rtsp_client import ConnectionClosedByServer
from doubles.video.rtsp_client import get_rtsp_stream
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from os_access import WindowsAccess
from tests.infra import assert_raises

_logger = logging.getLogger(__name__)


def _test_close_connection_on_session_expiration(distrib_url, two_vm_types, api_version, kill_session_on_server, camera_server_type, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    if camera_server_type == 'mpjpeg':
        camera_server = MultiPartJpegCameraServer()
    elif camera_server_type == 'rtsp_mjpeg':
        camera_server = MjpegRtspCameraServer()
    else:
        raise RuntimeError(f"Unknown camera_server_type {camera_server_type}")
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    one = two_mediaservers.first.installation()
    two = two_mediaservers.second.installation()
    if isinstance(one.os_access, WindowsAccess):
        one.os_access.disable_netprofm_service()
    if isinstance(two.os_access, WindowsAccess):
        two.os_access.disable_netprofm_service()
    two_mediaservers.start()
    remote_session_update_sec = 5

    if one.specific_features().get('sessionLimitS') > 0:
        session_limit_name = 'sessionLimitS'
        session_limit_value = session_limit_sec = 60

    else:
        session_limit_name = 'sessionLimitMinutes'
        session_limit_value = 1
        session_limit_sec = 60

    for server in one, two:
        server.api.setup_local_system({
            # How often does the server check a token received on a remote (non-cloud) server.
            'remoteSessionUpdateS': remote_session_update_sec,
            # How long is the token valid.
            session_limit_name: session_limit_value,
            })
    merge_systems(one, two, take_remote_settings=False)
    [camera] = add_cameras(one, camera_server)
    if camera_server.protocol == 'http':
        first_stream_reader = partial(get_frames, one.api.mpjpeg_live_url(camera.id))
        second_stream_reader = partial(get_frames, two.api.mpjpeg_live_url(camera.id))
    elif camera_server.protocol == 'rtsp':
        time_limit_sec = 30 * 60  # Enough for the test
        first_stream_reader = partial(
            get_rtsp_stream,
            one.api.secure_rtsp_url(camera.id),  # SSL is required for Bearer authentication type
            time_limit_sec)
        second_stream_reader = partial(
            get_rtsp_stream,
            two.api.secure_rtsp_url(camera.id),  # SSL is required for Bearer authentication type
            time_limit_sec)
    else:
        raise RuntimeError(f"Unsupported camera server type {camera_server.__class__.__name__}")
    credentials = one.api.get_credentials()
    assert credentials.auth_type == 'bearer'
    auth_header = one.api.make_auth_header()
    exit_stack.enter_context(camera_server.async_serve())
    # Camera statuses may blink between 'Online' and 'Offline' immediately after starting.
    # Wait for them to stabilize.
    time.sleep(5)
    executor = exit_stack.enter_context(ThreadPoolExecutor(max_workers=2))
    first_stream_fut = executor.submit(first_stream_reader, auth_header=auth_header)
    second_stream_fut = executor.submit(second_stream_reader, auth_header=auth_header)
    time.sleep(5)
    assert first_stream_fut.running()
    time.sleep(5)
    assert second_stream_fut.running()
    if kill_session_on_server == 'first_server':
        one.api.remove_session(credentials.token)
    elif kill_session_on_server == 'second_server':
        two.api.remove_session(credentials.token)
    else:
        _logger.info("Wait %d seconds for the session to expire", session_limit_sec)
        time.sleep(session_limit_sec)
    wait_timeout_sec = remote_session_update_sec + 5
    with assert_raises((ConnectionClosed, ConnectionClosedByServer)):
        first_stream_fut.result(timeout=wait_timeout_sec)
    with assert_raises((ConnectionClosed, ConnectionClosedByServer)):
        second_stream_fut.result(timeout=wait_timeout_sec)
