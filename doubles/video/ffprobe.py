# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import logging
import os
import shlex
import statistics
import tempfile
import time
from collections import Counter
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime
from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from subprocess import DEVNULL
from subprocess import PIPE
from subprocess import Popen
from subprocess import SubprocessError
from subprocess import run
from typing import Any
from typing import List
from typing import Mapping
from typing import Optional
from xml.etree.ElementTree import XMLPullParser

from os_access.local_shell import local_shell

_logger = logging.getLogger(__name__)


@lru_cache()
def _find_ffprobe_exe():
    command = 'where' if os.name == 'nt' else 'which'
    outcome = run([command, 'ffprobe'], capture_output=True)
    locations = outcome.stdout.decode().strip().splitlines()
    if not locations:
        raise Exception(
            "Cannot find ffprobe; "
            "it's expected in PATH, because it doesn't have an installer; "
            "restart IDE or command line window to load new PATH")
    if len(locations) >= 2:
        raise Exception("Found multiple ffprobe: " + " ".join(locations))
    return 'ffprobe'


def make_ffprobe_command(media_url, frame_count=None, duration_sec=None):
    assert not (frame_count and duration_sec)
    command = [
        _find_ffprobe_exe(), '-of', 'csv=nokey=0', '-rtsp_transport', 'tcp', '-i', media_url,
        '-select_streams', 'v',
        '-show_entries', 'stream=codec_name:frame=pkt_pts_time,pkt_size',
        '-nofind_stream_info']
    if frame_count is not None:
        command += ['-read_intervals', f'%+#{frame_count}']
    elif duration_sec is not None:
        command += ['-read_intervals', f'%+{duration_sec}']
    return command


def wait_for_stream(media_url):
    # Get one frame to check if stream is available
    command = make_ffprobe_command(media_url, frame_count=1)
    start = time.monotonic()
    errors = ""
    timeout = 60
    while time.monotonic() - start < timeout:
        process = Popen(command, stdout=PIPE, stderr=PIPE)
        process_start = time.monotonic()
        while time.monotonic() - process_start < 20:
            if process.poll() is not None:
                break
            time.sleep(5)
        else:
            process.kill()
            errors += "No stdout\n"
            continue
        if process.returncode != 0:
            _, stderr = process.communicate()
            errors += f"{stderr.decode('ascii', 'backslashreplace')}\n"
            continue
        break
    else:
        raise RuntimeError(f"Failed to get single frame in {timeout} seconds. Errors:\n{errors}")


@contextmanager
def get_stream_async(media_url, duration_sec=30):
    command = make_ffprobe_command(media_url, duration_sec=duration_sec)
    process = Popen(command, stdout=DEVNULL, stderr=DEVNULL)
    try:
        yield
    finally:
        try:
            process.kill()
        except OSError:
            pass


def _load_media_info(media_path, options: List[str]):
    if str(media_path).startswith('rtsp'):
        options.extend(['-rtsp_transport', 'tcp'])
    command = [
        _find_ffprobe_exe(),
        '-hide_banner',
        '-loglevel', 'quiet',  # Do not show anything except json output
        '-print_format', 'json',
        *options,
        str(media_path),
        ]
    _logger.debug("Run command: '%s'", shlex.join(command))
    result = run(command, capture_output=True)
    _logger.debug("Output:\n%s", result.stdout.decode('utf-8'))
    if result.returncode != 0:
        raise RuntimeError(
            f"ffprobe returned non-zero exit code: {result.returncode}. Stderr: {result.stderr}")
    return json.loads(result.stdout)


def get_stream_info(media_path):
    media_info = _load_media_info(media_path, options=['-show_streams'])
    return media_info['streams']


def get_media_format_info(media_path):
    media_info = _load_media_info(media_path, options=['-show_format'])
    return media_info['format']


def video_is_valid(path: Path) -> bool:
    try:
        local_shell.run(['ffmpeg', '-i', str(path), '-f', 'null', '-'])
    except SubprocessError:
        return False
    return True


def read_video_file_with_start_time_metadata(file: Path, timestamp_sec: float) -> bytes:
    fd, path = tempfile.mkstemp(suffix='.mkv')
    out_path = Path(path)
    try:
        command = [
            'ffmpeg',
            '-i', str(file),
            '-codec', 'copy',
            '-metadata', 'START_TIME=%s' % int(timestamp_sec * 1000),
            '-y',
            str(out_path),
            ]
        local_shell.run(command)
        return out_path.read_bytes()
    finally:
        try:
            os.close(fd)
        except OSError:
            # Descriptor has already been closed
            pass
        out_path.unlink()


class FfprobeError(Exception):
    pass


class FfprobeNoStreamsError(FfprobeError):
    pass


class _FfprobeXmlParser:
    """ffprobe XML parser.

    XML output works correctly, supports streaming and is easiest to parse.
    A stream parser can handle abruptly closed streams.
    csv and csv=nokey=0 are broken: https://trac.ffmpeg.org/ticket/7153
    """

    def __init__(self):
        self._xml_parser = XMLPullParser(events=['start'])
        self._result = defaultdict(list)

    def feed(self, stdout):
        self._xml_parser.feed(stdout)
        counter = Counter()
        for event, element in self._xml_parser.read_events():
            assert event == 'start'
            if element.tag not in ('stream', 'frame'):
                continue
            label = element.tag + 's'  # Label is singular, i.e 'frame', 'stream', etc. Should be plural
            self._result[label].append(element.attrib)
            counter[label] += 1
        return {**counter}

    def result(self):
        return self._result


def _format(pid, buffer):
    buffer = 'closed' if buffer is None else buffer.decode('ascii', 'backslashreplace')
    return '\n'.join(f'pid={pid}: ' + line for line in buffer.rstrip().splitlines())


class _FfprobeCommand:

    def __init__(
            self,
            stream_url,
            command_arguments,
            *,
            timeout,
            synchronous: bool = False):
        self._command = [
            _find_ffprobe_exe(),
            '-of', 'xml',
            '-i', stream_url,
            *command_arguments,
            ]
        if stream_url.startswith('rtsp'):
            self._command.extend(['-rtsp_transport', 'tcp'])
        self._timeout = timeout
        self._synchronous = synchronous

    def _get_output(self):
        with local_shell.Popen(self._command) as process:
            pid = process.pid
            _logger.debug('Run async pid=%s: %s', pid, ' '.join(self._command))
            stderr = bytearray()
            started_at = time.monotonic()

            while True:
                receive_timeout = 1 if self._synchronous else 0
                stdout_chunk, stderr_chunk = process.receive(receive_timeout)
                if stdout_chunk is None and stderr_chunk is None:
                    break
                _logger.debug(
                    "Process pid=%s: in progress;\n"
                    "new stdout:\n%s\n"
                    "new stderr:\n%s\n",
                    pid, _format(pid, stdout_chunk), _format(pid, stderr_chunk))
                stderr.extend(stderr_chunk if stderr_chunk is not None else b'')
                worked_for = time.monotonic() - started_at
                if worked_for > self._timeout:
                    process.kill()
                    raise FfprobeError(
                        f"Timed out {worked_for}/{self._timeout}: "
                        f"{self._command}")
                yield stdout_chunk

            _logger.debug('Process pid=%s -- stderr:\n%s', pid, _format(pid, stderr))
            process.wait()
            assert process.returncode is not None
            if process.returncode != 0:
                raise FfprobeError(
                    f"Non-zero exit status {process.returncode}: "
                    f"{self._command}")

    def process_output(self):
        parser = _FfprobeXmlParser()
        for stdout in self._get_output():
            update_summary = parser.feed(stdout)
            yield {'stdout_len': len(stdout), 'parsed': update_summary}
        return parser.result()


def ffprobe_get_audio_codec(stream_url):
    command = _FfprobeCommand(
        stream_url,
        ['-show_streams', '-select_streams', 'a'],
        timeout=5)
    output = yield from command.process_output()
    if not output['streams']:
        raise FfprobeNoStreamsError("No streams found in ffprobe output")
    audio_codec = output['streams'][0]['codec_name'].upper()
    return audio_codec


def ffprobe_watch_video_stream(stream_url, video_length_sec):
    command = _FfprobeCommand(
        stream_url,
        [
            '-nofind_stream_info',
            '-select_streams', 'v',
            '-show_entries', 'stream=codec_name:frame=pkt_pts_time',
            '-read_intervals', f'%+{video_length_sec}',
            ],
        timeout=video_length_sec + 30)
    result = yield from command.process_output()
    if 'frames' not in result:
        raise FfprobeError("No frames were extracted by ffprobe.")
    watched_sec = float(result['frames'][-1]['pkt_pts_time'])
    return watched_sec


def _get_stream_bitrate_and_fps(frames):
    if len(frames) < 10:
        _logger.debug("Too few frames to compute bitrate and FPS")
        return 0, 0
    # VMS-16769: Skip corrupted first I frame and its GOP.
    # Count only full GOPs for higher precision.
    i_frame_indices = [i for i, f in enumerate(frames) if f['pict_type'] == 'I']
    try:
        [_skipped_i_frame_idx, begin_idx, *_, end_idx] = i_frame_indices
    except ValueError:  # Not enough GOPs
        begin_idx = 1
        end_idx = len(frames) - 1
    if frames[begin_idx]['pkt_pts_time'] == 'N/A':
        raise ValueError(
            f"No pkt_pts_time in {frames[begin_idx]['pict_type']}-frame number {begin_idx + 1}")
    begin_pts_sec = float(frames[begin_idx]['pkt_pts_time'])
    end_pts_sec = float(frames[end_idx]['pkt_pts_time'])
    duration_sec = end_pts_sec - begin_pts_sec
    fps = (end_idx - begin_idx) / duration_sec
    total_bytes = sum(int(f['pkt_size']) for f in frames[begin_idx:end_idx])
    bitrate_kbps = total_bytes / duration_sec * 8 / 1000
    return bitrate_kbps, fps


def _actual_video_params(output):
    stream = output['streams'][0]
    frames = output['frames']
    for frame in reversed(frames):
        pts = frame.get('pkt_pts_time')
        if pts is None:
            continue
        duration_sec = float(pts)
        break
    else:
        duration_sec = 0
    codec = stream['codec_name'].upper()
    stream_frames = defaultdict(list)
    for frame in frames:
        stream_frames[frame['stream_index']].append(frame)
    all_streams_params = [_get_stream_bitrate_and_fps(sf) for sf in stream_frames.values()]
    bitrate_list, fps_list = zip(*all_streams_params)
    bitrate_kbps = statistics.mean(bitrate_list)
    fps = statistics.mean(fps_list)
    return {
        'codec': codec,
        'resolution': {
            'width': int(frames[0]['width']),
            'height': int(frames[0]['height']),
            'stream_count': len(all_streams_params),
            },
        'fps': fps,
        'bitrate_kbps': bitrate_kbps,
        'duration_sec': duration_sec,
        }


def ffprobe_get_video_stream(stream_url, frames_to_check: Optional = None):
    if frames_to_check:
        frames_to_check_args = ['-read_intervals', f'%+#{frames_to_check}']
    else:
        frames_to_check_args = []
    command = _FfprobeCommand(
        stream_url,
        [
            '-nofind_stream_info',  # Do not analyze stream, it could take very long time
            '-select_streams', 'v',
            # -read_intervals takes effect only if it is last and -show_entries is present.
            '-show_entries',
            'stream=codec_name:frame=width,height,pkt_pts_time,pkt_size,pict_type,stream_index',
            *frames_to_check_args,
            ],
        timeout=60,
        )
    output = yield from command.process_output()
    if 'frames' not in output:
        raise FfprobeError("No frames were extracted by ffprobe.")
    if frames_to_check is not None and len(output['frames']) < frames_to_check * 0.8:
        # There can be less frames than requested
        raise FfprobeError(
            f"ffprobe returned less frames than requested: "
            f"requested {frames_to_check}, got {len(output['frames'])};")
    return _actual_video_params(output)


def watch_whole_stream(stream_url: str) -> Mapping[str, Any]:
    command = _FfprobeCommand(
        stream_url,
        [
            '-nofind_stream_info',  # Do not analyze stream, it could take very long time
            '-show_entries',
            'stream=codec_type,codec_name:frame=pkt_pts_time',
            ],
        timeout=60,
        synchronous=True)
    command_gen = command.process_output()
    while True:
        try:
            next(command_gen)
        except StopIteration as e:
            output = e.value
            break
    if 'frames' not in output:
        raise FfprobeError("No frames were extracted by ffprobe")
    duration_sec = float(output['frames'][-1]['pkt_pts_time'])
    return {
        'duration_sec': duration_sec,
        'streams': output['streams'],
        }


def extract_start_timestamp(path):
    info = _load_media_info(path, options=['-show_format'])
    tags = info['format']['tags']
    possible_timestamp_fields = [
        'START_TIME',
        'creation_time',
        'date',
        'comment',
        ]
    for field in possible_timestamp_fields:
        try:
            value = tags[field]
        except KeyError:
            continue
        if field == 'creation_time':
            start_time = datetime.strptime(value, '%Y-%m-%dT%H:%M:%S.%f%z')
            return int(start_time.timestamp() * 1_000)
        elif field == 'comment':
            comment = json.loads(value)
            return int(comment['startTimeMs'])
        else:
            return int(value)
    else:
        raise RuntimeError(f"Cannot get timestamp from {path}")


class SampleMediaFile:

    def __init__(self, path):
        self.path = path
        info = _load_media_info(path, options=['-show_streams', '-show_format'])
        duration = info['format'].get('duration')
        if duration is not None:
            self.duration = timedelta(seconds=float(duration))
        else:
            self.duration = None
        [stream] = info['streams']  # single stream is expected in media sample
        self.width = stream['width']  # int
        self.height = stream['height']  # int
        bit_rate = info['format'].get('bit_rate')
        if bit_rate is not None:
            self.bit_rate = int(bit_rate)
        else:
            self.bit_rate = None
        x, y = stream['avg_frame_rate'].split('/')  # "30/1"
        self.fps = int(x) / int(y)

    def __repr__(self):
        duration = f'duration {self.duration}' if self.duration is not None else 'undefined duration'
        bitrate = f'bitrate {self.bit_rate / 1024**2} Mbps' if self.bit_rate is not None else 'undefined bitrate'
        return f'<SampleMediaPath {self.path!r} with {duration}, fps {self.fps}, {bitrate}'
