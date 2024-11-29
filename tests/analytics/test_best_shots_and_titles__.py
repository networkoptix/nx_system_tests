# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from abc import ABCMeta
from abc import abstractmethod
from contextlib import AbstractContextManager
from contextlib import ExitStack
from contextlib import contextmanager
from pathlib import Path
from pathlib import PurePosixPath
from typing import Mapping
from typing import Optional
from typing import Sequence
from uuid import UUID

import cv2
import numpy

from _internal.service_registry import default_prerequisite_store
from doubles.software_cameras import H264RtspCameraServer
from doubles.software_cameras import JpegImage
from doubles.video.ffprobe import SampleMediaFile
from installation import ClassicInstallerSupplier
from installation import Mediaserver
from mediaserver_api import CameraStatus
from mediaserver_api import MediaserverApi
from mediaserver_api.analytics import AnalyticsTrack
from mediaserver_api.analytics import NormalizedRectangle
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from tests.analytics.common import check_for_plugin_diagnostic_events
from tests.analytics.common import enable_device_agent
from tests.analytics.common import prepare_one_mediaserver_stand
from tests.analytics.common import record_analytics_tracks

_logger = logging.getLogger(__name__)

LOCAL_TEST_FILE = 'best-shot-test/test_1_32x32.jpg'
URL_TEST_FILE = 'best-shot-test/test_2_32x32.jpg'
AREA_REFERENCE_FRAME_IMAGE = 'best-shot-test/4_pictures_screenshot.png'
VIDEO_FILE = 'best-shot-test/4_pictures.264'


def _test_best_shots_and_titles(
        distrib_url: str,
        vm_type: str,
        api_version: str,
        exit_stack: ExitStack,
        with_plugins_from_release: Optional[str] = None,
        ):
    stand = prepare_one_mediaserver_stand(
        distrib_url, vm_type, api_version, exit_stack, with_plugins_from_release)
    if with_plugins_from_release == '5.1.5':
        titles_supported = False
    else:
        titles_supported = ClassicInstallerSupplier(distrib_url).distrib().newer_than('vms_6.0')
    stand.os_access().networking.allow_hosts([default_prerequisite_store.hostname()])
    media_sample = SampleMediaFile(default_prerequisite_store.fetch(VIDEO_FILE))
    mediaserver = stand.mediaserver()
    camera_id = exit_stack.enter_context(
        sample_video_recording_camera_id(mediaserver, media_sample))
    errors = {}
    local_reference_file = default_prerequisite_store.fetch(LOCAL_TEST_FILE)
    filename = PurePosixPath(LOCAL_TEST_FILE).name
    vm_local_reference_path = mediaserver.os_access.tmp() / filename
    vm_local_reference_path.write_bytes(local_reference_file.read_bytes())
    engine_collection = mediaserver.api.get_analytics_engine_collection()
    engine = engine_collection.get_stub('Best Shots', 'Best Shots and Titles')
    enable_device_agent(mediaserver.api, engine.name(), camera_id)
    exit_stack.callback(
        check_for_plugin_diagnostic_events, mediaserver.api)
    mediaserver.api.set_device_analytics_settings(
        device_id=camera_id,
        engine_id=engine.id(),
        settings_values={
            'enableBestShotGeneration': True,
            'enableObjectTitleGeneration': False,
            # Generate the bests shot early: avoid requesting not yet existing
            # best shots for fresh tracks.
            'frameNumberToGenerateBestShot': 0,
            },
        )
    local_frame_file = default_prerequisite_store.fetch(AREA_REFERENCE_FRAME_IMAGE)
    area_errors = _frame_area_best_shot_errors(
        api=mediaserver.api,
        camera_id=camera_id,
        engine_id=engine.id(),
        full_frame_image=local_frame_file,
        )
    if area_errors:
        errors['best_shot_area_errors'] = area_errors
    _logger.info(
        "Set Best Shots generation policy to local image; image path: %s", vm_local_reference_path)
    local_errors = _best_shot_from_image_errors(
        api=mediaserver.api,
        engine_id=engine.id(),
        camera_id=camera_id,
        generation_policy='local',
        reference_path=str(vm_local_reference_path),
        reference_image=JpegImage(vm_local_reference_path.read_bytes()),
        )
    if local_errors:
        errors['best_shot_local_image'] = local_errors
    url_reference_file = default_prerequisite_store.fetch(URL_TEST_FILE)
    image_url = default_prerequisite_store.url(URL_TEST_FILE)
    _logger.info(
        "Set Best Shots generation policy to URL; image URL: %s", image_url)
    url_errors = _best_shot_from_image_errors(
        api=mediaserver.api,
        engine_id=engine.id(),
        camera_id=camera_id,
        generation_policy='url',
        reference_path=image_url,
        reference_image=JpegImage(url_reference_file.read_bytes()),
        )
    if url_errors:
        errors['best_shot_image_url'] = url_errors
    if titles_supported:
        mediaserver.api.set_device_analytics_settings(
            device_id=camera_id,
            engine_id=engine.id(),
            settings_values={
                'enableBestShotGeneration': False,
                'enableObjectTitleGeneration': True,
                },
            )
        title_from_local_image_errors = _title_from_local_image_errors(
            api=mediaserver.api,
            camera_id=camera_id,
            engine_id=engine.id(),
            image_path=vm_local_reference_path,
            )
        if title_from_local_image_errors:
            errors['title_from_local_image'] = title_from_local_image_errors
        title_from_image_url_errors = _title_from_image_url_errors(
            api=mediaserver.api,
            camera_id=camera_id,
            engine_id=engine.id(),
            image_url=image_url,
            reference=url_reference_file,
            )
        if title_from_image_url_errors:
            errors['title_from_image_url'] = title_from_image_url_errors
        frame_area_title_image_errors = _frame_area_title_image_errors(
            api=mediaserver.api,
            camera_id=camera_id,
            engine_id=engine.id(),
            full_frame_image=local_frame_file,
            )
        if frame_area_title_image_errors:
            errors['frame_area_title_image'] = frame_area_title_image_errors
        title_text_errors = _text_title_errors(
            api=mediaserver.api,
            camera_id=camera_id,
            engine_id=engine.id(),
            )
        if title_text_errors:
            errors['title_text'] = title_text_errors
    assert not errors, f"Errors encountered: {errors!r}"


@contextmanager
def sample_video_recording_camera_id(
        mediaserver: Mediaserver, media_sample: SampleMediaFile) -> AbstractContextManager[UUID]:
    _logger.info("Using %s file for software camera server", media_sample.path)
    camera_server = H264RtspCameraServer(
        source_video_file=media_sample.path,
        fps=media_sample.fps,
        )
    api = mediaserver.api
    [camera] = add_cameras(mediaserver, camera_server)
    api.enable_secondary_stream(camera.id)
    with camera_server.async_serve():
        api.start_recording(camera.id)
        api.wait_for_camera_status(camera.id, CameraStatus.RECORDING)
        yield camera.id
        api.stop_recording(camera.id)


def _best_shot_from_image_errors(
        api: MediaserverApi,
        engine_id: UUID,
        camera_id: UUID,
        generation_policy: str,
        reference_path: str,
        reference_image: JpegImage,
        ) -> Sequence[str]:
    errors = []
    new_agent_settings = {
        'local': {
            'bestShotGenerationPolicy': 'imageBestShotGenerationPolicy',
            'image': reference_path,
            # VMS-51841: Setting key names were changed after the support for Titles was added.
            'bestShotImage': reference_path,
            },
        'url': {
            'bestShotGenerationPolicy': 'urlBestShotGenerationPolicy',
            'url': reference_path,
            # VMS-51841: Setting key names were changed after the support for Titles was added.
            'bestShotUrl': reference_path,
            },
        }
    api.set_device_analytics_settings(
        device_id=camera_id,
        engine_id=engine_id,
        settings_values=new_agent_settings[generation_policy],
        )
    all_tracks = record_tracks_with_best_shots(api=api, best_shot_track_count=3)
    # Skip first track, new settings can be applied after the first track's best shot is generated
    all_tracks.pop(0)
    for tracks in all_tracks:
        best_shot_image = JpegImage(
            api.get_analytics_track_best_shot_image(camera_id, tracks.track_id()))
        if best_shot_image == reference_image:
            _logger.info(
                "Best shot image %s matches with reference image %s",
                best_shot_image, reference_image)
            continue
        error_msg = (
            f"Best shot image {best_shot_image} is different from reference {reference_image}")
        _logger.warning(error_msg)
        errors.append(error_msg)
    return errors


class OpenCvImage:

    def __init__(self, base):
        self.base = base
        [self.height_px, self.width_px, *_] = self.base.shape

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.width_px}x{self.height_px}>"

    @classmethod
    def from_file(cls, src_image_file: Path):
        return cls(cv2.imread(str(src_image_file)))

    @classmethod
    def from_byte_string(cls, byte_string):
        numpy_array = numpy.frombuffer(byte_string, numpy.uint8)
        return cls(cv2.imdecode(numpy_array, cv2.IMREAD_COLOR))

    def crop_area(self, area: NormalizedRectangle):
        x_start = int(self.width_px * area.x.start)
        x_end = int(self.width_px * area.x.end)
        y_start = int(self.height_px * area.y.start)
        y_end = int(self.height_px * area.y.end)
        return OpenCvImage(self.base[y_start: y_end, x_start: x_end])

    def _sift_matches(self, other, max_match_distance=200):
        # https://docs.opencv.org/4.x/da/df5/tutorial_py_sift_intro.html
        # https://www.analyticsvidhya.com/blog/2019/10/detailed-guide-powerful-sift-technique-image-matching-python/  # noqa
        sift_detector = cv2.SIFT_create()
        [_, self_descriptors] = sift_detector.detectAndCompute(self.base, None)
        [_, other_descriptors] = sift_detector.detectAndCompute(other.base, None)
        bruteforce_matcher = cv2.BFMatcher(cv2.NORM_L2, crossCheck=True)
        matches = bruteforce_matcher.match(self_descriptors, other_descriptors)
        best_matches = list(filter(lambda x: x.distance <= max_match_distance, matches))
        _logger.info(
            "Found %d matches with distance not greater than %f",
            len(best_matches), max_match_distance)
        return best_matches

    def is_similar(self, other):
        # Determined empirically. If the number of matches is not less than
        # matches_threshold we can reliably state that the images are similar
        matches_threshold = 100
        if self.width_px != other.width_px or self.height_px != other.height_px:
            return False
        if len(self._sift_matches(other)) < matches_threshold:
            return False
        return True


def _frame_area_best_shot_errors(
        api: MediaserverApi,
        camera_id: UUID,
        engine_id: UUID,
        full_frame_image: Path,
        ) -> Sequence[str]:
    _logger.info("Set Best Shots generation policy to area")
    agent_settings = api.set_device_analytics_settings(
        device_id=camera_id,
        engine_id=engine_id,
        settings_values={
            'bestShotGenerationPolicy': 'fixedBoundingBoxBestShotGenerationPolicy',
            },
        )
    default_area = _best_shot_rect_from_agent_settings(agent_settings)
    best_shot_rect_cls = default_area.__class__
    areas = [
        best_shot_rect_cls(x=0.5, y=0.5, width=0.5, height=0.5),
        best_shot_rect_cls(x=0, y=0, width=0.5, height=0.5),
        best_shot_rect_cls(x=0, y=0.7, width=0.4, height=0.25),
        best_shot_rect_cls(x=0, y=0, width=1, height=1),  # Full frame
        ]
    errors = []
    full_frame_cv2 = OpenCvImage.from_file(full_frame_image)
    for area in areas:
        api.set_device_analytics_settings(
            device_id=camera_id,
            engine_id=engine_id,
            settings_values=area.as_dict(),
            )
        _logger.info("Recording analytics tracks for area %s", area.as_dict())
        # Skip a few tracks: new settings might take effect not instantly.
        [*_, track] = record_tracks_with_best_shots(api, best_shot_track_count=3)
        if not track.best_shot().rectangle().is_close_to(area):
            errors.append(
                f"Track {track.track_id()} best shot area is {track.best_shot().rectangle()!r}, "
                f"expected {area!r}")
            continue
        best_shot_bytes = api.get_analytics_track_best_shot_image(camera_id, track.track_id())
        best_shot_cv2 = OpenCvImage.from_byte_string(best_shot_bytes)
        reference_cv2 = full_frame_cv2.crop_area(area)
        if not best_shot_cv2.is_similar(reference_cv2):
            errors.append(
                f"Track's {track.track_id()} best shot {best_shot_cv2} for {area} does not match "
                f"with reference {reference_cv2} cropped from {full_frame_cv2} using same area")
    return errors


def record_tracks_with_best_shots(api: MediaserverApi, best_shot_track_count: int = 1):
    started_at = time.monotonic()
    timeout = best_shot_track_count * 15
    tracks = record_analytics_tracks(api, best_shot_track_count, timeout)
    while True:
        best_shot_tracks = [t for t in tracks if t.best_shot().exists()]
        if len(best_shot_tracks) >= best_shot_track_count:
            return best_shot_tracks
        if time.monotonic() > started_at + timeout:
            raise TimeoutError(
                f"Only {len(best_shot_tracks)}/{len(tracks)} have "
                f"best shots after {timeout} sec. At least {best_shot_track_count} expected.")
        time.sleep(1)
        tracks = [
            *best_shot_tracks,
            *[api.get_analytics_track(t.track_id()) for t in tracks if t not in best_shot_tracks],
            ]
        tracks = sorted(tracks, key=lambda t: t.time_period().start_ms)


class _StubBestShotAndTitleRectangle(NormalizedRectangle, metaclass=ABCMeta):

    @abstractmethod
    def as_dict(self):
        pass

    @classmethod
    @abstractmethod
    def from_setting_values(cls, setting_values: Mapping):
        pass


class _OldBestShotRectangle(_StubBestShotAndTitleRectangle):

    def as_dict(self):
        return {
            'topLeftX': self.x.start,
            'topLeftY': self.y.start,
            'width': self.x.size,
            'height': self.y.size,
            }

    @classmethod
    def from_setting_values(cls, setting_values: Mapping):
        return cls(
            x=setting_values['topLeftX'],
            y=setting_values['topLeftY'],
            width=setting_values['width'],
            height=setting_values['height'],
            )


class _NewBestShotRectangle(_StubBestShotAndTitleRectangle):
    """VMS-52893: Server, Analytics, Stub: Add bounding box to Object Titles."""

    def as_dict(self):
        return {
            'bestShotTopLeftX': self.x.start,
            'bestShotTopLeftY': self.y.start,
            'bestShotWidth': self.x.size,
            'bestShotHeight': self.y.size,
            }

    @classmethod
    def from_setting_values(cls, setting_values: Mapping):
        return cls(
            x=setting_values['bestShotTopLeftX'],
            y=setting_values['bestShotTopLeftY'],
            width=setting_values['bestShotWidth'],
            height=setting_values['bestShotHeight'],
            )


def _best_shot_rect_from_agent_settings(
        agent_settings: MediaserverApi.DeviceAnalyticsSettings):
    settings_values = agent_settings.values
    if 'topLeftX' in settings_values.keys():
        return _OldBestShotRectangle.from_setting_values(settings_values)
    return _NewBestShotRectangle.from_setting_values(settings_values)


def _record_track_with_title_image(api: MediaserverApi) -> Optional[AnalyticsTrack]:
    # In ~5% cases 1st and 2nd tracks lack title image after enabling title with image generation.
    [_, _, track, *_] = record_analytics_tracks(api=api, required_track_count=3)
    timeout = 30
    started_at = time.monotonic()
    while True:
        if track.title() is None:
            # Return early: if the track does not have a title at all it will never obtain it.
            _logger.warning("No title for analytics track %r was found", track)
            return None
        if track.title().has_image():
            _logger.debug("Found analytics track %r with title image", track)
            return track
        if time.monotonic() > started_at + timeout:
            _logger.warning(
                "No title image for analytics track %r found after %d sec", track, timeout)
            return None
        _logger.debug(
            "Track %r doesn't have title image; try re-fetching track in 1 sec", track)
        time.sleep(1)
        track = api.get_analytics_track(track.track_id())


def _title_from_local_image_errors(api, camera_id: UUID, engine_id: UUID, image_path: Path):
    _logger.info("Use local image %s for analytics track title", image_path)
    api.set_device_analytics_settings(
        device_id=camera_id,
        engine_id=engine_id,
        settings_values={
            'titleGenerationPolicy': 'imageTitleGenerationPolicy',
            'titleImage': str(image_path),
            },
        )
    track = _record_track_with_title_image(api)
    if track is None:
        return "No track with title image found"
    title_bytes = api.get_analytics_track_title_image(
        camera_id=camera_id,
        track_id=track.track_id(),
        )
    title_jpeg_image = JpegImage(title_bytes)
    reference_jpeg_image = JpegImage(image_path.read_bytes())
    if title_jpeg_image != reference_jpeg_image:
        return (
            f"Track {track.track_id()} title image {title_jpeg_image} does not match "
            f"with reference {reference_jpeg_image}")
    return ""


def _title_from_image_url_errors(
        api, camera_id: UUID, engine_id: UUID, image_url: str, reference: Path):
    _logger.info("Use image url %s for analytics track title", image_url)
    api.set_device_analytics_settings(
        device_id=camera_id,
        engine_id=engine_id,
        settings_values={
            'titleGenerationPolicy': 'urlTitleGenerationPolicy',
            'titleUrl': image_url,
            },
        )
    track = _record_track_with_title_image(api)
    if track is None:
        return "No track with title image found"
    title_bytes = api.get_analytics_track_title_image(
        camera_id=camera_id,
        track_id=track.track_id(),
        )
    title_jpeg_image = JpegImage(title_bytes)
    reference_jpeg_image = JpegImage(reference.read_bytes())
    if title_jpeg_image != reference_jpeg_image:
        return (
            f"Track {track.track_id()} title image {title_jpeg_image} does not match "
            f"with reference {reference_jpeg_image}")
    return ""


def _frame_area_title_image_errors(
        api: MediaserverApi,
        camera_id: UUID,
        engine_id: UUID,
        full_frame_image: Path,
        ) -> Sequence[str]:
    _logger.info("Set Title generation policy to area")
    api.set_device_analytics_settings(
        device_id=camera_id,
        engine_id=engine_id,
        settings_values={
            'titleGenerationPolicy': 'fixedBoundingBoxTitleGenerationPolicy',
            },
        )
    areas = [
        _TitleBoundingBoxRectangle(x=0.5, y=0.5, width=0.5, height=0.5),
        _TitleBoundingBoxRectangle(x=0, y=0, width=0.5, height=0.5),
        _TitleBoundingBoxRectangle(x=0, y=0.7, width=0.4, height=0.25),
        _TitleBoundingBoxRectangle(x=0, y=0, width=1, height=1),  # Full frame
        ]
    errors = []
    full_frame_cv2 = OpenCvImage.from_file(full_frame_image)
    for area in areas:
        api.set_device_analytics_settings(
            device_id=camera_id,
            engine_id=engine_id,
            settings_values=area.as_dict(),
            )
        _logger.info("Recording analytics tracks for title from area %s", area.as_dict())
        track = _record_track_with_title_image(api)
        if track is None:
            errors.append(f"Area {area.as_dict()}: no track with title image found")
        if not track.title().rectangle().is_close_to(area):
            errors.append(
                f"Track {track.track_id()} title area is {track.title().rectangle()!r}, "
                f"expected {area!r}")
            continue
        title_bytes = api.get_analytics_track_title_image(camera_id, track.track_id())
        title_cv2 = OpenCvImage.from_byte_string(title_bytes)
        reference_cv2 = full_frame_cv2.crop_area(area)
        if not title_cv2.is_similar(reference_cv2):
            errors.append(
                f"Track's {track.track_id()} title image {title_cv2} for {area} does not match "
                f"with reference {reference_cv2} cropped from {full_frame_cv2} using same area")
    return errors


def _text_title_errors(
        api: MediaserverApi,
        camera_id: UUID,
        engine_id: UUID,
        ):
    expected_text = "This is test title name"
    api.set_device_analytics_settings(
        device_id=camera_id,
        engine_id=engine_id,
        settings_values={
            'titleText': expected_text,
            },
        )
    _logger.info("Recording analytics tracks for title with text %s", expected_text)
    # Skip first track(-s): new settings might be applied later than it started.
    [_, track, *_] = record_analytics_tracks(api=api, required_track_count=2)
    if track.title() is None:
        return f"Track {track.track_id()} does not have a title"
    if track.title().text() != expected_text:
        return f"Track {track.track_id()} title text is {track.title().text()}; expected {expected_text}"
    return ""


class _TitleBoundingBoxRectangle(_StubBestShotAndTitleRectangle):

    def as_dict(self):
        return {
            'titleTopLeftX': self.x.start,
            'titleTopLeftY': self.y.start,
            'titleWidth': self.x.size,
            'titleHeight': self.y.size,
            }

    @classmethod
    def from_setting_values(cls, setting_values: Mapping):
        return cls(
            x=setting_values['titleTopLeftX'],
            y=setting_values['titleTopLeftY'],
            width=setting_values['titleWidth'],
            height=setting_values['titleHeight'],
            )
