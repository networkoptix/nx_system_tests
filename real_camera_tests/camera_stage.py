# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import hashlib
import logging
import time
import urllib.parse
from abc import ABCMeta
from abc import abstractmethod
from contextlib import contextmanager
from datetime import datetime
from ipaddress import ip_address
from typing import Callable
from typing import Collection
from typing import Generator
from typing import Iterable
from typing import NamedTuple
from typing import Optional
from typing import Sequence
from typing import Union
from urllib.parse import parse_qsl
from urllib.parse import urlparse

from directories.prerequisites import PrerequisiteStore
from doubles.video import vlc_server
from installation import Mediaserver
from mediaserver_api import CameraStatus
from mediaserver_api import MediaserverApiConnectionError
from mediaserver_api import MediaserverApiHttpError
from mediaserver_api import MediaserverApiReadTimeout
from real_camera_tests.checks import Failure
from real_camera_tests.checks import Halt
from real_camera_tests.checks import PythonExceptionResult
from real_camera_tests.checks import Result
from real_camera_tests.checks import Skipped
from real_camera_tests.checks import Success
from real_camera_tests.checks import TimedOut
from real_camera_tests.checks import expect_values
from real_camera_tests.reporter import CheckResults

_logger = logging.getLogger(__name__)


class VideoConfig:
    _known_codecs = ['H264', 'H265', 'MJPEG', 'MP4', 'VP8']
    _known_qualities = ['highest', 'normal']  # TODO: Add others if necessary.
    _default_quality = 'highest'
    assert _default_quality in _known_qualities
    _default_frames_to_check = 125

    def __init__(
            self,
            codec,
            width,
            height,
            fps=None,
            set_bitrate_kbps=None,
            rec_quality=_default_quality,
            frames_to_check=_default_frames_to_check,
            after_auto=False,
            export_duration_sec=None,
            transcoded_export_formats=(),
            ):
        codec = codec.upper()
        if codec not in self._known_codecs:
            raise ValueError(f"Unknown codec {codec}")
        if rec_quality not in self._known_qualities:
            raise ValueError(f"Unknown quality {rec_quality}")
        self.codec: str = codec
        self.resolution: str = f'{width}x{height}'
        self.width: int = width
        self.height: int = height
        self.fps: Optional[int] = fps
        self.set_bitrate_kbps: Optional[float] = set_bitrate_kbps
        self.rec_quality = rec_quality
        self.after_auto: bool = after_auto
        self.frames_to_check: int = frames_to_check
        self.export_duration_sec = export_duration_sec
        self.transcoded_export_formats = [f.upper() for f in transcoded_export_formats]

    def with_half_fps(self):
        return self.__class__(
            self.codec,
            self.width,
            self.height,
            self.fps // 2,
            self.set_bitrate_kbps,
            self.rec_quality,
            self.frames_to_check,
            self.after_auto,
            )

    @property
    def name(self):
        result = f"{self.codec} {self.width}x{self.height}"
        if self.fps is not None:
            result += f" {self.fps}"
        if self.set_bitrate_kbps is not None:
            result += f" {self.set_bitrate_kbps}"
        if self.after_auto:  # TODO: Remove this mimicked nonsense behavior.
            result += f" {self.after_auto}"
        return result

    def webm_vp8_export_config(self, duration_sec):
        return VideoConfig(
            codec='VP8',
            fps=self.fps,
            export_duration_sec=duration_sec,
            width=_round_to_closest(self.width, 16),
            height=_round_to_closest(self.height, 4),
            )

    def original_codec_export_config(self, duration_sec):
        return VideoConfig(
            codec=self.codec,
            width=self.width,
            height=self.height,
            fps=self.fps,
            export_duration_sec=duration_sec,
            )

    def mpjpeg_mjpeg_export_config(self, duration_sec):
        return VideoConfig(
            codec='MJPEG',
            # There are no timestamps in MJPEG and it's not possible to evaluate fps basing on it.
            # Client (ffprobe) sets default values that correspond to 25 fps.
            fps=25,
            export_duration_sec=duration_sec,
            width=_round_to_closest(self.width, 16),
            height=_round_to_closest(self.height, 4),
            )


class AudioConfig:

    def __init__(self, codec, skip_codec_change=False, set_codec=None):
        self.codec = codec.upper()
        self.skip_codec_change = skip_codec_change
        self.set_codec = set_codec.upper() if set_codec is not None else self.codec

    @property
    def name(self):
        return (
            f"audio_stream: codec {self.codec}, skip_codec_change: {self.skip_codec_change}, "
            f"set_codec: {self.set_codec}")


class _IoPinConfig(NamedTuple):

    pin_name: str
    id: Union[str, int]
    channel: int


class IoInputConfig(_IoPinConfig):

    @property
    def name(self):
        return f"Alarm input: name: {self.pin_name}, id: {self.id}, channel: {self.channel}"


class IoOutputConfig(_IoPinConfig):

    @property
    def name(self):
        return f"Alarm output: name: {self.pin_name}, id: {self.id}, channel: {self.channel}"


class OldIoInputConfig(NamedTuple):

    id: str
    name: str = None
    connected_out_id: str = None


class OldIoOutputConfig(NamedTuple):

    id: str
    name: str = None


def _round_down(number, factor):
    remainder = number % factor
    return number - remainder


def _round_up(number, factor):
    remainder = number % factor
    if remainder == 0:
        return number
    return number + (factor - remainder)


def _round_to_closest(number, factor):
    remainder = number % factor
    if 2 * remainder < factor:
        return _round_down(number, factor)
    else:
        return _round_up(number, factor)


class _PhysicalId:

    def __init__(self, auto, manual):
        self.auto = auto
        self.manual = manual


class SamePhysicalId(_PhysicalId):

    def __init__(self, physical_id):
        super(SamePhysicalId, self).__init__(physical_id, physical_id)


class DifferentPhysicalIds(_PhysicalId):

    def __init__(self, auto, manual):
        super(DifferentPhysicalIds, self).__init__(auto, manual)


class ManualOnlyPhysicalId(_PhysicalId):

    def __init__(self, manual):
        super(ManualOnlyPhysicalId, self).__init__(auto=None, manual=manual)


class CameraConfig:
    recording_status: CameraStatus

    def __init__(
            self,
            name,
            hostname,
            discovery_url,
            physical_id: _PhysicalId,
            primary_default,
            primary_custom=(),
            secondary_default=(),
            secondary_custom=(),
            stream_urls=None,
            audio=(),
            logical_id=None,
            credentials=None,
            attributes=None,
            resource_params_to_set=None,
            ):
        self.stream_urls: StreamUrlsCheck = stream_urls
        self.type = 'Camera'
        self.name = name
        self.physical_id = physical_id
        self.logical_id = logical_id
        self.id = self.logical_id if self.logical_id is not None else self.physical_id.auto
        self.has_credentials = credentials is not None
        if self.has_credentials:
            [self.user, self.password] = [credentials.get('login'), credentials.get('password')]
        else:
            [self.user, self.password] = [None, None]
        self.discovery_url = discovery_url
        self.hostname = hostname
        self.attributes = attributes
        self.primary_default = primary_default
        self.primary_custom = primary_custom
        self.secondary_default = secondary_default
        self.secondary_custom = secondary_custom
        self.audio = audio
        self.export_configs = {}
        self.primary_export_configs = self._create_video_configs_for_export(
            [*self.primary_default, *self.primary_custom])
        self.secondary_export_configs = self._create_video_configs_for_export(
            [*self.secondary_default, *self.secondary_custom])
        self.resource_params_to_set = resource_params_to_set

    class _ExportVideoConfigs(NamedTuple):
        original_codec: VideoConfig
        webm_vp8: Optional[VideoConfig]
        mpjpeg_mjpeg: Optional[VideoConfig]

    def _create_video_configs_for_export(self, all_configs: Collection):
        duration_sec = 15
        if not all_configs:
            return None
        configs_with_transcoding = []
        for config in all_configs:
            if config.transcoded_export_formats:
                configs_with_transcoding.append(config)
        if not configs_with_transcoding:
            [*_, tested_config] = all_configs
            return self._ExportVideoConfigs(
                original_codec=tested_config.original_codec_export_config(duration_sec),
                webm_vp8=None,
                mpjpeg_mjpeg=None,
                )
        if len(configs_with_transcoding) > 1:
            raise RuntimeError(
                f"0 or 1 configs with transcoded_export_formats expected, "
                f"{len(configs_with_transcoding)} found")
        [tested_config] = configs_with_transcoding
        if not set(tested_config.transcoded_export_formats).issubset({'WEBM', 'MPJPEG'}):
            raise ValueError(
                f"Some of transcoded_export_formats "
                f"{tested_config.transcoded_export_formats} are unexpected,"
                f"supported formats are: 'WEBM', 'MPJPEG' (case-insensitive)")
        if 'WEBM' in tested_config.transcoded_export_formats:
            webm_vp8_export_config = tested_config.webm_vp8_export_config(duration_sec)
        else:
            webm_vp8_export_config = None
        if 'MPJPEG' in tested_config.transcoded_export_formats:
            mpjpeg_mjpeg_export_config = tested_config.mpjpeg_mjpeg_export_config(duration_sec)
        else:
            mpjpeg_mjpeg_export_config = None
        return self._ExportVideoConfigs(
            original_codec=tested_config.original_codec_export_config(duration_sec),
            webm_vp8=webm_vp8_export_config,
            mpjpeg_mjpeg=mpjpeg_mjpeg_export_config,
            )


class GenericLinkConfig(CameraConfig):
    recording_status = CameraStatus.RECORDING

    def __init__(
            self,
            name,
            logical_id,
            physical_id: ManualOnlyPhysicalId,
            url: str,
            attributes,
            primary_default,
            audio,
            ):
        assert physical_id.manual == hashlib.md5(url.encode()).hexdigest().lower()
        url_parsed = urllib.parse.urlparse(url)
        hostname = url_parsed.hostname
        self._validate_hostname(hostname)
        super().__init__(
            name,
            logical_id=logical_id,
            hostname=hostname,
            discovery_url=url,
            physical_id=physical_id,
            attributes=attributes,
            primary_default=primary_default,
            stream_urls=ExpectedStreamUrls(url),
            audio=audio,
            resource_params_to_set={'rtpTransport': 'UDP'},
            )
        self.port = url_parsed.port
        self._filename = url_parsed.path.lstrip('/')

    @staticmethod
    def _validate_hostname(hostname):
        """Hostname is a name; IP would depend on the local settings."""
        try:
            ip_address(hostname)
        except ValueError:
            pass
        else:
            raise Exception("Use a hostname, not an IP in generic links")

    @contextmanager
    def serving(self, store: PrerequisiteStore, bind_ip='0.0.0.0'):
        file_path = store.fetch(self._filename)
        _logger.info("Attempting to play a file {}".format(file_path))
        with vlc_server.rtsp_serving(
                video_file=file_path,
                port=self.port,
                url_path=self._filename,
                host_ip=bind_ip,
                audio=True,
                user=self.user,
                password=self.password,
                ):
            yield


class PtzPoint(NamedTuple):

    pan: float
    tilt: float
    zoom: float

    def as_dict(self):
        return {'pan': self.pan, 'tilt': self.tilt, 'zoom': self.zoom}


class PtzPosition(NamedTuple):

    point: PtzPoint = None
    preset_id: str = None
    preset_name: str = None


class PtzConfig(NamedTuple):

    missing_capabilities: Collection = []
    positions: Sequence[PtzPosition] = []
    is_logical: bool = False
    float_abs_error: float = 0.01
    speed: int = 100
    use_native_presets: bool = False


class RealDeviceConfig(CameraConfig):

    def __init__(
            self,
            name,
            ip_address,
            physical_id: _PhysicalId,
            primary_default,
            primary_custom=(),
            secondary_default=(),
            secondary_custom=(),
            stream_urls=None,
            audio=(),
            logical_id=None,
            credentials=None,
            attributes=None,
            resource_params_to_set=None,
            ins=(),
            outs=(),
            new_ins=(),
            new_outs=(),
            ptz: PtzConfig = None,
            ):
        if ptz is not None:
            if ptz.use_native_presets:
                use_native_preset_resource_param = {'userPreferredPtzPresetType': 'native'}
                if resource_params_to_set is None:
                    resource_params_to_set = use_native_preset_resource_param
                else:
                    resource_params_to_set = {
                        **resource_params_to_set, **use_native_preset_resource_param}
        super().__init__(
            name=name,
            hostname=ip_address,
            physical_id=physical_id,
            discovery_url=ip_address,
            primary_default=primary_default,
            primary_custom=primary_custom,
            stream_urls=stream_urls,
            secondary_default=secondary_default,
            secondary_custom=secondary_custom,
            audio=audio,
            logical_id=logical_id,
            credentials=credentials,
            attributes=attributes,
            resource_params_to_set=resource_params_to_set,
            )
        # TODO: Require at least either ins or outs or both.
        self.ins = ins
        self.outs = outs
        # For new_io_stage: IO check involving RPi.GPIO
        self.new_ins = new_ins
        self.new_outs = new_outs
        self.ptz = ptz


class SingleRealCameraConfig(RealDeviceConfig):
    recording_status = CameraStatus.RECORDING

    def __init__(
            self,
            name,
            ip_address,
            physical_id: _PhysicalId,
            primary_default,
            primary_custom=(),
            secondary_default=(),
            secondary_custom=(),
            stream_urls=None,
            audio=(),
            logical_id=None,
            credentials=None,
            attributes=None,
            resource_params_to_set=None,
            ins=(),
            outs=(),
            new_ins=(),
            new_outs=(),
            ptz: PtzConfig = None,
            ):
        super().__init__(
            name=name,
            ip_address=ip_address,
            physical_id=physical_id,
            primary_default=primary_default,
            primary_custom=primary_custom,
            secondary_default=secondary_default,
            secondary_custom=secondary_custom,
            stream_urls=stream_urls,
            audio=audio,
            logical_id=logical_id,
            credentials=credentials,
            attributes=attributes,
            resource_params_to_set=resource_params_to_set,
            ins=ins,
            outs=outs,
            new_ins=new_ins,
            new_outs=new_outs,
            ptz=ptz,
            )


class OnvifMedia2SingleCameraConfig(SingleRealCameraConfig):

    def __init__(
            self,
            name,
            ip_address,
            physical_id: _PhysicalId,
            primary_default,
            primary_custom=(),
            secondary_default=(),
            secondary_custom=(),
            stream_urls=None,
            audio=(),
            logical_id=None,
            credentials=None,
            attributes=None,
            ins=(),
            outs=(),
            new_ins=(),
            new_outs=(),
            ptz: PtzConfig = None,
            ):
        super().__init__(
            name=name,
            ip_address=ip_address,
            physical_id=physical_id,
            primary_default=primary_default,
            primary_custom=primary_custom,
            secondary_default=secondary_default,
            secondary_custom=secondary_custom,
            stream_urls=stream_urls,
            audio=audio,
            logical_id=logical_id,
            credentials=credentials,
            attributes=attributes,
            resource_params_to_set={'useMedia2ToFetchProfiles': 'useIfSupported'},
            ins=ins,
            outs=outs,
            new_ins=new_ins,
            new_outs=new_outs,
            ptz=ptz,
            )


class EncoderConfig(RealDeviceConfig):
    recording_status = CameraStatus.RECORDING

    def __init__(
            self,
            name,
            ip_address,
            physical_id: _PhysicalId,
            primary_default,
            primary_custom=(),
            secondary_default=(),
            secondary_custom=(),
            stream_urls=None,
            audio=(),
            logical_id=None,
            credentials=None,
            attributes=None,
            ins=(),
            outs=(),
            new_ins=(),
            new_outs=(),
            ptz: PtzConfig = None,
            ):
        super().__init__(
            name=name,
            ip_address=ip_address,
            physical_id=physical_id,
            primary_default=primary_default,
            primary_custom=primary_custom,
            secondary_default=secondary_default,
            secondary_custom=secondary_custom,
            stream_urls=stream_urls,
            audio=audio,
            logical_id=logical_id,
            credentials=credentials,
            attributes=attributes,
            ins=ins,
            outs=outs,
            new_ins=new_ins,
            new_outs=new_outs,
            ptz=ptz,
            )
        self.type = 'Encoder'


class NvrChannelConfig(RealDeviceConfig):
    recording_status = CameraStatus.ONLINE

    def __init__(
            self,
            name,
            ip_address,
            physical_id: _PhysicalId,
            channel,
            primary_custom=(),
            secondary_custom=(),
            stream_urls=None,
            audio=(),
            logical_id=None,
            credentials=None,
            attributes=None,
            ins=(),
            outs=(),
            new_ins=(),
            new_outs=(),
            ptz: PtzConfig = None,
            ):
        super().__init__(
            name=name,
            ip_address=ip_address,
            physical_id=physical_id,
            primary_default=[],
            primary_custom=primary_custom,
            secondary_default=[],
            secondary_custom=secondary_custom,
            stream_urls=stream_urls,
            audio=audio,
            logical_id=logical_id,
            credentials=credentials,
            attributes=attributes,
            ins=ins,
            outs=outs,
            new_ins=new_ins,
            new_outs=new_outs,
            ptz=ptz,
            )
        self.type = 'NVR'
        self.channel = channel
        # NVR records only 1 stream and by default primary stream is recorded
        self.export_configs['secondary'] = None


class NvrFirstChannelConfig(NvrChannelConfig):

    def __init__(
            self,
            name,
            ip_address,
            physical_id: _PhysicalId,
            channel,
            channel_count,
            primary_custom=(),
            secondary_custom=(),
            stream_urls=None,
            audio=(),
            logical_id=None,
            credentials=None,
            attributes=None,
            ins=(),
            outs=(),
            new_ins=(),
            new_outs=(),
            ptz: PtzConfig = None,
            ):
        super().__init__(
            name=name,
            ip_address=ip_address,
            physical_id=physical_id,
            channel=channel,
            primary_custom=primary_custom,
            secondary_custom=secondary_custom,
            stream_urls=stream_urls,
            audio=audio,
            logical_id=logical_id,
            credentials=credentials,
            attributes=attributes,
            ins=ins,
            outs=outs,
            new_ins=new_ins,
            new_outs=new_outs,
            ptz=ptz,
            )
        self.channel_count = channel_count
        assert self.channel == 1


class NvrAnotherChannelConfig(NvrChannelConfig):
    recording_status = CameraStatus.ONLINE

    def __init__(
            self,
            name,
            ip_address,
            physical_id: _PhysicalId,
            channel,
            primary_custom=(),
            secondary_custom=(),
            stream_urls=None,
            audio=(),
            logical_id=None,
            credentials=None,
            attributes=None,
            ins=(),
            outs=(),
            new_ins=(),
            new_outs=(),
            ptz: PtzConfig = None,
            ):
        super().__init__(
            name=name,
            ip_address=ip_address,
            physical_id=physical_id,
            channel=channel,
            primary_custom=primary_custom,
            secondary_custom=secondary_custom,
            stream_urls=stream_urls,
            audio=audio,
            logical_id=logical_id,
            credentials=credentials,
            attributes=attributes,
            ins=ins,
            outs=outs,
            new_ins=new_ins,
            new_outs=new_outs,
            ptz=ptz,
            )
        assert self.channel >= 2
        assert self.physical_id.auto.endswith(f'_channel={self.channel}')


class Run:
    """Several consecutive stages for a camera.

    Runs between server stages, which are kind of common baselines.
    Keeps and updates a camera object.
    """

    def __init__(self, server: Mediaserver, config: CameraConfig):
        self.server = server
        self.name = config.name
        self.id = config.id  # Changed from outside.
        self.config = config
        self._uuid: Optional[str] = None
        self._data: Optional[dict] = None

    @property
    def uuid(self):
        if self._uuid is None and self.data is not None:
            self._uuid = self.data.id
        return self._uuid

    @property
    def data(self):
        try:
            camera = self.server.api.get_camera(self.id, is_uuid=False)
        except (MediaserverApiHttpError, MediaserverApiConnectionError):
            camera = None
        self._data = self._data or camera

        return self._data

    def clear_cache(self):
        self._data = None


ResultGenerator = Generator[Result, None, Union[Success, Failure, Skipped]]
ResultGeneratorFactory = Callable[[Run], ResultGenerator]


class BaseStage(metaclass=ABCMeta):

    @abstractmethod
    def make_executors(
            self, camera_config: CameraConfig,
            ) -> Sequence['StageExecutor']:
        pass


class Stage(BaseStage):
    """Stage object. Common for all cameras.

    Creates an individual stage executor for a camera.
    """

    def __init__(
            self,
            run_function: Optional[ResultGeneratorFactory],
            timeout: float = 30,
            ):
        self.timeout = timeout
        self._actions = run_function

    def make_executors(
            self, camera_config: CameraConfig,
            ) -> Sequence['StageExecutor']:
        return [_FunctionStageExecutor(self._actions, self.timeout)]


class MultiStage(BaseStage):
    """Stage object. Common for all cameras.

    Creates multiple stage executors for a single camera.
    E.g. an executor for each video configuration.
    """

    def __init__(
            self,
            generate_function: Callable[[CameraConfig, float], Iterable['StageExecutor']],
            timeout: float = 30,
            ):
        self._name = generate_function.__name__
        self.timeout = timeout
        self._actions_generator = generate_function

    def make_executors(
            self, camera_config: CameraConfig,
            ) -> Sequence['StageExecutor']:
        return [*self._actions_generator(camera_config, self.timeout)]


class IoStage(BaseStage):

    def __init__(self, io_events_func, io_manager, timeout: float = 30):
        self.io_events_func = io_events_func
        self._io_manager = io_manager
        self.timeout = timeout

    def make_executors(
            self, camera_config: CameraConfig,
            ) -> Sequence['StageExecutor']:
        return [IoStageExecutor(self.io_events_func, self._io_manager, self.timeout)]


class StageExecutor(metaclass=ABCMeta):
    """Single stage for a single camera.

    Iterates through the steps. Yields after each.
    Defines and reports the result.
    """

    def __init__(
            self,
            name: str,
            timeout: float,
            ):
        self.name = name
        self._timeout = timeout

    @abstractmethod
    def _execute(self, run: Run):
        pass

    def steps(
            self,
            camera_config: CameraConfig,
            server: Mediaserver,
            hard_timeout: Optional[float] = None,
            ) -> Generator[None, None, Result]:
        timeout = min(self._timeout, hard_timeout) if hard_timeout else self._timeout
        run = Run(server, camera_config)
        stage_name = f'RCT/{camera_config.name}/{self.name}'
        _logger.info(
            "%s: %s: stage started: reported as %s",
            self.name, camera_config.name, stage_name)
        started_at = time.monotonic()
        steps = self._execute(run)
        last_result = Halt("Just started")
        while True:
            run.clear_cache()
            _logger.debug(
                "%s: %s: stage step starts",
                self.name, camera_config.name)
            try:
                res = next(steps)
            except MediaserverApiReadTimeout as e:
                if len(server.list_core_dumps()) < 5:
                    _logger.debug(
                        "%s: %s: stage step completed, "
                        "API request timed out, "
                        "stage will be finished, "
                        "generate core dumps",
                        self.name, camera_config.name)
                    server.take_backtrace('api_read_timeout_1')
                    _logger.debug(
                        "%s: %s: stage step completed, "
                        "first core dump generated",
                        self.name, camera_config.name)
                    yield  # Wait for a while before generating the next dump.
                    _logger.debug(
                        "%s: %s: stage step started, "
                        "generate second core dump",
                        self.name, camera_config.name)
                    server.take_backtrace('api_read_timeout_2')
                    _logger.error(
                        "%s: %s: stage finished, API request timed out, "
                        "core dumps generated: "
                        "exception: %r",
                        self.name, camera_config.name, e)
                else:
                    _logger.error(
                        "%s: %s: stage finished, API request timed out, "
                        "no core dumps, too many of them already: "
                        "exception: %r",
                        self.name, camera_config.name, e)
                return PythonExceptionResult(e)
            except MediaserverApiHttpError as error:
                _logger.error(
                    "%s: %s: stage finished, API exception: %r",
                    self.name, camera_config.name, error)
                return PythonExceptionResult(error)
            except StopIteration as e:
                _logger.info(
                    "%s: %s: stage finished, clean exit: %r",
                    camera_config.name, self.name, e.value.get_text_result())
                return e.value
            except Exception as e:
                _logger.info(
                    "%s: %s: stage finished, unexpected exception: %r",
                    camera_config.name, self.name, e)
                return PythonExceptionResult(e)
            assert not res.is_success()
            if res.can_be_final():
                _logger.info(
                    "%s: %s: stage step completed, can be final: %s",
                    camera_config.name, self.name, res.get_text_result())
                last_result = res
            else:
                _logger.info(
                    "%s: %s: stage step completed, non-final: %s",
                    camera_config.name, self.name, res.get_text_result())
                if not last_result.can_be_final():
                    last_result = res
            duration = time.monotonic() - started_at
            if duration > timeout:
                try:
                    steps.close()
                except Exception as e:
                    _logger.info(
                        "%s: %s: stage finished, failed closing generator: %r",
                        camera_config.name, self.name, e)
                    return PythonExceptionResult(e)
                else:
                    _logger.info(
                        "%s: %s: stage timeout: %s/%s",
                        camera_config.name, self.name, duration, timeout)
                    result = TimedOut(timeout, duration, last_result)
                    return result
            yield


class _FunctionStageExecutor(StageExecutor):

    def __init__(self, function: ResultGeneratorFactory, timeout: float):
        super().__init__(function.__name__, timeout)
        self._function = function

    def _execute(self, run: Run):
        return (yield from self._function(run))


class IoStageExecutor(StageExecutor):

    def __init__(self, io_events_function, io_manager, timeout: float):
        super().__init__(io_events_function.__name__, timeout)
        self.io_events_function = io_events_function
        self._io_manager = io_manager

    def _execute(self, run: Run):
        return (yield from self.io_events_function(run, self._io_manager))


def make_camera_step_generator(
        server: Mediaserver,
        discovery_stage: BaseStage,
        stages: Sequence[BaseStage],
        camera_config: CameraConfig,
        stage_hard_timeout: float,
        check_results: CheckResults,
        ):
    # Preferring logicalId over physicalId
    discovery_stage_executor: StageExecutor
    discovery_stage_executors = discovery_stage.make_executors(camera_config)
    # There can be 0 or 1 discovery_stage_executor
    if not discovery_stage_executors:
        _logger.info("%s: no discovery stage found, skipped_stages=%r", camera_config.name, stages)
        return
    [discovery_stage_executor] = discovery_stage_executors
    discovery_started_at_utc = datetime.utcnow()
    check_results.update_result(
        device_name=camera_config.name,
        stage_name=discovery_stage_executor.name,
        result=Halt("Just started"),
        started_at_iso=discovery_started_at_utc.isoformat(' ', 'microseconds'),
        )
    discovery_result = yield from discovery_stage_executor.steps(
        camera_config,
        server,
        stage_hard_timeout,
        )
    check_results.update_result(
        device_name=camera_config.name,
        stage_name=discovery_stage_executor.name,
        result=discovery_result,
        duration_sec=(datetime.utcnow() - discovery_started_at_utc).seconds,
        )
    if not discovery_result.is_success():
        _logger.error(
            "%s: %s: discovery stage failed, skipped_stages=%r",
            camera_config.name, discovery_stage_executor.name, stages)
        return
    stage_executors: Sequence[StageExecutor] = []
    for current_stage in stages:
        stage_executors += current_stage.make_executors(camera_config)
    _logger.info('%s: %d stages', camera_config.name, len(stage_executors))
    for executor in stage_executors:
        executor_started_at_utc = datetime.utcnow()
        check_results.update_result(
            device_name=camera_config.name,
            stage_name=executor.name,
            result=Halt("Just started"),
            started_at_iso=executor_started_at_utc.isoformat(' ', 'microseconds'),
            )
        executor_result = yield from executor.steps(camera_config, server, stage_hard_timeout)
        check_results.update_result(
            device_name=camera_config.name,
            stage_name=executor.name,
            result=executor_result,
            duration_sec=(datetime.utcnow() - executor_started_at_utc).seconds,
            )


class StreamUrlsCheck(metaclass=ABCMeta):

    @abstractmethod
    def check(self, camera, hostname):
        pass


class ExpectedStreamUrls(StreamUrlsCheck):

    def __init__(self, primary, secondary=None):
        self._primary = primary
        self._secondary = secondary

    def check(self, camera, hostname):
        expected = {}
        # Not using enumerate() to match with Mediaserver's streamUrls format and to utilize
        # Checker.expect_dict() that does not accept int as dict keys
        for key, raw_url in [('1', self._primary), ('2', self._secondary)]:
            if raw_url is None:
                continue
            expected[key] = _normalize_url(raw_url.replace('{ip_address}', hostname))
        actual = {key: _normalize_url(raw_url) for key, raw_url in camera.stream_urls.items()}
        return expect_values(expected, actual, syntax='*')


class AlternativeStreamUrls(StreamUrlsCheck):

    def __init__(self, *checkers: ExpectedStreamUrls):
        self._checkers = checkers

    def check(self, camera, hostname):
        errors = []
        for checker in self._checkers:
            check_errors = checker.check(camera, hostname)
            if check_errors:
                errors.append(check_errors)
        if len(errors) == len(self._checkers):
            return errors
        return []


def _normalize_url(raw: str):
    parsed = urlparse(raw)
    queries = parse_qsl(parsed.query)
    # Currently we are not working with URLs with non-empty params and fragment components
    # of urllib.parse.ParseResult. If such URLs appear, the code can be easily updated
    return {
        'scheme': parsed.scheme,
        'hostname': parsed.hostname,
        'port': parsed.port,
        'path': parsed.path,
        'query': sorted(queries),
        }
