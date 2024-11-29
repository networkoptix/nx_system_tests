# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from statistics import median
from typing import Collection
from typing import Iterable
from typing import Optional
from typing import Sequence

from doubles.dnssd import DNSSDScope
from doubles.software_cameras import CameraServer
from installation import Mediaserver
from mediaserver_api import BaseCamera
from mediaserver_api import CameraStatus
from mediaserver_api import MediaserverApi
from mediaserver_api import TimePeriod

_logger = logging.getLogger(__name__)


class PeriodsWithGaps(Exception):
    pass


def add_cameras(
        mediaserver: Mediaserver,
        camera_server: CameraServer,
        indices: Sequence[int] = (0,),
        user: Optional[str] = None,
        password: Optional[str] = None,
        ) -> Sequence[BaseCamera]:
    mediaserver_api = mediaserver.api
    server_address = mediaserver.os_access.source_address()
    existing_urls = [c.url for c in mediaserver_api.list_cameras()]
    camera_urls = []
    for camera_index in indices:
        camera_url = '{}://{}:{}/{}.{}'.format(
            camera_server.protocol,
            server_address,
            camera_server.port,
            camera_index,
            camera_server.codec,
            )
        if camera_url not in existing_urls:
            camera_urls.append(camera_url)
    gen = mediaserver_api.add_cameras_manually(*camera_urls, user=user, password=password)
    next(gen)
    while True:
        camera_server.serve(time_limit_sec=1)
        try:
            next(gen)
        except StopIteration as e:
            camera_list = e.value
            # The list contains cameras in arbitrary order.
            return sorted(camera_list, key=lambda camera: camera.url)


def record_from_cameras(
        mediaserver_api: MediaserverApi,
        cameras: Iterable[BaseCamera],
        camera_server: CameraServer,
        duration_sec: float,
        force_disconnect=True,
        ) -> Sequence[TimePeriod]:
    camera_ids = [camera.id for camera in cameras]
    old_periods = mediaserver_api.list_recorded_periods(camera_ids)
    primary_paths = [c.path for c in cameras]
    secondary_paths = [c.secondary_path for c in cameras if c.secondary_path is not None]
    mediaserver_api.start_recording(*camera_ids)
    _logger.debug("Wait for all cameras status to become '%s'", CameraStatus.RECORDING)
    started_at = time.monotonic()
    while True:
        camera_server.serve(time_limit_sec=0.1)
        cameras = [c for c in mediaserver_api.list_cameras() if c.id in camera_ids]
        recording_camera_count = len([c for c in cameras if c.status == CameraStatus.RECORDING])
        passed_sec = time.monotonic() - started_at
        _logger.debug(
            "%d/%d cameras got '%s' status after %.2f seconds",
            recording_camera_count,
            len(camera_ids),
            CameraStatus.RECORDING,
            passed_sec)
        if recording_camera_count == len(camera_ids):
            break
        if passed_sec > 10:
            raise RuntimeError("Cameras recording didn't start after 10 seconds")
    camera_server.clean_up()  # Remove disconnected sockets from previous runs
    started_at = time.monotonic()
    while True:
        camera_server.serve(time_limit_sec=1)
        seconds_streamed = camera_server.get_durations_sec(primary_paths + secondary_paths)
        seconds_passed = time.monotonic() - started_at
        _logger.debug(
            "Seconds streamed: %r\nSeconds passed: %r; Timeout: %r",
            seconds_streamed,
            seconds_passed,
            duration_sec,
            )
        if all(seconds >= duration_sec for seconds in seconds_streamed):
            break
        timeout_sec = duration_sec + 3  # Extra seconds to compensate possible camera server lags
        if time.monotonic() - started_at > timeout_sec:
            raise RuntimeError(f"Cameras recording didn't finish after {duration_sec:.2f} seconds")
    for camera_id in camera_ids:
        mediaserver_api.stop_recording(camera_id)
    if force_disconnect:
        camera_server.disconnect_all()
    else:
        camera_server.wait_until_all_disconnect(timeout_sec=30)
    new_periods_list = mediaserver_api.list_recorded_periods(
        camera_ids,
        timeout_sec=30,
        incomplete_ok=False,
        empty_ok=False,
        skip_periods=old_periods,
        )
    periods_with_gaps = {
        camera_id: camera_periods
        for camera_id, camera_periods in zip(camera_ids, new_periods_list)
        if len(camera_periods) > 1}
    if periods_with_gaps:  # Mediaserver must consolidate time periods with zero gaps
        gaps_plain_list = []
        gaps_message = ""
        for camera_id, camera_periods in periods_with_gaps.items():
            first_period_duration = camera_periods[0].duration_sec
            gaps_message += f"\nCamera {camera_id}: recorded {first_period_duration:4.1f} sec"
            gaps_list = TimePeriod.calculate_gaps(camera_periods)  # Zero gaps are also disallowed
            gaps_plain_list.extend(gaps_list)
            for gap, period in zip(gaps_list, camera_periods[1:]):
                gaps_message += f", gap {gap:4.1f} sec, recorded {period.duration_sec:4.1f} sec"
        raise PeriodsWithGaps(
            "There are gaps in recorded periods; "
            f"cameras with gaps count: {len(periods_with_gaps)}; "
            f"min {min(gaps_plain_list):.1f} sec; max: {max(gaps_plain_list):.1f} sec; "
            f"median: {median(gaps_plain_list):.1f} sec;"
            + gaps_message)
    return [p for [p] in new_periods_list]


def serve_until_status(mediaserver_api, camera_id, camera_server, expected_status, timeout_sec=60):
    started_at = time.monotonic()
    while time.monotonic() - started_at <= timeout_sec:
        current_status = mediaserver_api.get_camera(camera_id).status
        if current_status == expected_status:
            return
        camera_server.serve(time_limit_sec=2)
    raise RuntimeError(
        f"Timed out ({timeout_sec} seconds) waiting for camera {expected_status!r} status; "
        f"Current status: {current_status!r}")


class MediaserversDNSSDScope(DNSSDScope):
    """Unicast address collection taken from Mediaservers.

    Usually, the multicast IP address is used.
    Using unicast address instead is a workaround for cases where
    the multicast address cannot be used because of networking schemes,
    that cannot forward non-unicast traffic (e.g. VBox intnet).
    """

    def __init__(self, mediaservers: Collection[Mediaserver]):
        super().__init__([
            (mediaserver.os_access.address, mediaserver.os_access.get_port('udp', 5353))
            for mediaserver in mediaservers
            ])
