# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import math
import time
from abc import ABCMeta
from abc import abstractmethod
from datetime import datetime
from datetime import timedelta
from datetime import tzinfo
from math import sqrt
from pathlib import PurePath
from pathlib import PurePosixPath
from typing import Sequence
from typing import Tuple
from typing import Union

from doubles.video.ffprobe import SampleMediaFile
from doubles.video.ffprobe import read_video_file_with_start_time_metadata
from mediaserver_api import TimePeriod

_logger = logging.getLogger(__name__)


class MediaserverArchive:

    def __init__(
            self,
            video_archive_files: 'ArchiveDirectory',
            ):
        self._video_archive_files = video_archive_files

    def __repr__(self):
        return f'<{self.__class__.__name__} on {self._video_archive_files!r}>'

    def with_name(self, folder_name: str):
        new_video_archive_files = self._video_archive_files.with_name(folder_name)
        return MediaserverArchive(new_video_archive_files)

    def exchange_contents(self, other: 'MediaserverArchive'):
        self._video_archive_files.exchange_contents(other._video_archive_files)

    # TODO: Used only once plus doesn't belong in this class. To be removed.
    def has_object_detection_db(self) -> bool:
        return self._video_archive_files.file_exists('object_detection.sqlite')

    def size_bytes(self) -> int:
        return self._video_archive_files.files_size_sum_bytes('.mkv')

    def camera_archive(self, physical_id) -> 'CameraArchive':
        return CameraArchive(physical_id, self._video_archive_files)

    def has_mkv_files(self) -> bool:
        return len(self._video_archive_files.search_file_recursively('.', '*.mkv')) > 0

    def storage_root_path(self) -> str:
        """
        Returns the parent path of the archive directory.

        There is no identifier for specifying storage in the Mediaserver API,
        so we use the parent path.
        """
        return self._video_archive_files.get_parent()

    def remove_info_files(self):
        rel_results = self._video_archive_files.search_file_recursively('..', 'info.txt')
        for info_file in rel_results:
            self._video_archive_files.unlink_file(info_file)


class CameraArchive:

    def __init__(self, physical_id: str, video_archive_files: 'ArchiveDirectory'):
        self._id = physical_id
        self._video_archive_files = video_archive_files

    def low(self) -> 'VideoArchive':
        new_video_archive_files = self._video_archive_files.new_facade(['low_quality', self._id])
        return VideoArchive(new_video_archive_files)

    def high(self) -> 'VideoArchive':
        new_video_archive_files = self._video_archive_files.new_facade(['hi_quality', self._id])
        return VideoArchive(new_video_archive_files)

    def size_bytes(self) -> int:
        return self.low().size_bytes() + self.high().size_bytes()

    def remove(self) -> None:
        _logger.debug("Remove archive for camera %s", self._id)
        self.low().remove()
        self.high().remove()

    # TODO: Used only once plus doesn't belong in this class. To be removed.
    def has_analytics_data_files(self) -> bool:
        subdir = PurePosixPath('archive', 'metadata', self._id)
        return len(self._video_archive_files.search_file_recursively(subdir, 'analytics_detailed_data.bin')) > 0

    # TODO: Used only once plus doesn't belong in this class. To be removed.
    def has_analytics_index_files(self) -> bool:
        subdir = PurePosixPath('archive', 'metadata', self._id)
        return len(self._video_archive_files.search_file_recursively(subdir, 'analytics_detailed_index.bin')) > 0

    def save_media_sample(self, start_time, sample):
        self.low().save_media_sample(start_time, sample)
        self.high().save_media_sample(start_time, sample)


class VideoArchive:

    def __init__(self, video_archive_files: 'ArchiveDirectory'):
        self._video_archive_files = video_archive_files

    def list_sorted_mkv(self) -> Sequence[PurePath]:
        return sorted(self._video_archive_files.search_file_recursively('.', '*.mkv'))

    def make_gap_in_archive(self, minimum_gap_sec: int = 11) -> Tuple[TimePeriod, int]:
        chunks = self.list_sorted_mkv()
        if len(chunks) < minimum_gap_sec:
            raise RuntimeError(
                f"There are not enough chunks to make a gap: {len(chunks)} < {minimum_gap_sec}")
        saved_chunks_count = len(chunks) - minimum_gap_sec
        first_removed_chunk_number = saved_chunks_count // 2
        last_removed_chunk_number = first_removed_chunk_number + minimum_gap_sec
        removed_chunks = chunks[first_removed_chunk_number:last_removed_chunk_number]
        for chunk in removed_chunks:
            self._video_archive_files.unlink_file(chunk)
        removed_chunks_names = [c.name for c in removed_chunks]
        [gap_period] = TimePeriod.list_from_filenames(removed_chunks_names)
        return gap_period, len(removed_chunks)

    def size_bytes(self) -> int:
        return self._video_archive_files.files_size_sum_bytes('.mkv')

    # TODO: Rework after class Periods is introduced
    def list_periods(self) -> Sequence[TimePeriod]:
        """List consolidated periods taken from archive directory.

        >>> fake_files_facade = FakeArchiveDirectory()
        >>> fake_files_facade.create_fake_file(PurePosixPath('50000_1000.mkv'), 1000)
        >>> fake_files_facade.create_fake_file(PurePosixPath('51000_1000.mkv'), 1000)
        >>> fake_files_facade.create_fake_file(PurePosixPath('54000_1000.mkv'), 1000)
        >>> archive = VideoArchive(fake_files_facade)
        >>> archive.list_periods()
        [TimePeriod(start_ms=50000, duration_ms=2000), TimePeriod(start_ms=54000, duration_ms=1000)]
        """
        filenames = [file.name for file in self.list_sorted_mkv()]
        periods = TimePeriod.list_from_filenames(filenames)
        _logger.debug("Periods: %r", periods)
        return periods

    def remove(self) -> None:
        self._video_archive_files.remove_dir()

    def _construct_chunk_path(
            self,
            start_time: datetime,
            duration: timedelta,
            ) -> PurePosixPath:
        """Construct MKV file path.

        Server stores media data in this format, using local time for directory parts:
        > <data dir>/
        >   <{hi_quality,low_quality}>/<camera-mac>/
        >     <year>/<month>/<day>/<hour>/
        >       <start,unix timestamp ms>_<duration,ms>.mkv
        For example:
        > server/var/data/data/
        >   low_quality/urn_uuid_b0e78864-c021-11d3-a482-f12907312681/
        >     2017/01/27/12/1485511093576_21332.mkv
        """
        machine_timezone = self._video_archive_files.get_timezone()
        local_dt = start_time.astimezone(machine_timezone)
        duration_ms = int(duration.total_seconds() * 1000)
        start_ms = int(start_time.timestamp() * 1000)
        return PurePosixPath(
            f'{local_dt.year:02d}',
            f'{local_dt.month:02d}',
            f'{local_dt.day:02d}',
            f'{local_dt.hour:02d}',
            f'{start_ms}_{duration_ms}.mkv',
            )

    def add_fake_record(
            self,
            start_time: datetime,
            duration_sec: float,
            bitrate_bps: int = 68 * 10**6,  # 4K 60 FPS
            chunk_duration_sec: int = 90,
            ) -> TimePeriod:
        [quotient, remainder] = divmod(duration_sec, chunk_duration_sec)
        for i in range(int(quotient)):
            chunk_start_time = start_time + timedelta(seconds=i * chunk_duration_sec)
            self._add_fake_chunk(bitrate_bps, chunk_start_time, chunk_duration_sec)
        if remainder > 0:  # TODO: Add a little threshold.
            chunk_start_time = start_time + timedelta(seconds=quotient * chunk_duration_sec)
            self._add_fake_chunk(bitrate_bps, chunk_start_time, remainder)
        # TODO: Update return value after class Periods is introduced
        return TimePeriod.from_datetime(start_time, timedelta(seconds=duration_sec))

    def _add_fake_chunk(self, bitrate_bps: float, start_time: datetime, duration_sec: float):
        duration = timedelta(seconds=duration_sec)
        path_parts = self._construct_chunk_path(start_time, duration)
        self._video_archive_files.create_fake_file(path_parts, int(duration_sec * bitrate_bps / 8))

    def has_info(self) -> bool:
        timeout_sec = 15  # Determined empirically
        started_at = time.monotonic()
        while True:
            if self._video_archive_files.file_exists('info.txt'):
                return True
            if time.monotonic() > started_at + timeout_sec:
                return False
            time.sleep(1)

    # TODO: This is a video module dependency and has to be removed
    def save_media_sample(self, start_time: datetime, sample: SampleMediaFile) -> None:
        if start_time.tzinfo is None:
            raise ValueError("Naive datetime is forbidden, use UTC or the local timezone")
        contents = read_video_file_with_start_time_metadata(sample.path, start_time.timestamp())
        path_parts = self._construct_chunk_path(start_time, sample.duration)
        _logger.info('Storing media sample %r', sample.path)
        self._video_archive_files.write_file(path_parts, contents)


def measure_usage_ratio(server, first_archive_path, second_archive_path):
    first_archive = server.archive(first_archive_path)
    second_archive = server.archive(second_archive_path)
    first_recorded = first_archive.size_bytes()
    second_recorded = second_archive.size_bytes()
    total_recorded = first_recorded + second_recorded
    ratio = first_recorded / total_recorded
    _logger.info(
        "Actual (measured) usage ratio (first / total) %.1fM / %.1fM = %.3f",
        first_recorded / 1024**2, total_recorded / 1024**2, ratio)
    return ratio


def usage_ratio_is_close(measured, first_effective, second_effective, chunk_count):
    # It's a Bernoulli process, results have the binomial distribution.
    total_effective = first_effective + second_effective
    expected_ratio = first_effective / total_effective
    std_dev = sqrt(chunk_count * expected_ratio * (1 - expected_ratio))
    # With many chunks, the normal distribution is a reasonable approximation,
    # where 3 std dev include 99.7%.
    tolerance = 3 * std_dev / chunk_count
    _logger.info(
        "Expected usage ratio (first / total) %.1fG / %.1fG = %.3f (+/-%.3f)",
        first_effective / 1024**3, total_effective / 1024**3,
        expected_ratio, tolerance)
    return math.isclose(measured, expected_ratio, abs_tol=tolerance)


class ArchiveDirectory(metaclass=ABCMeta):

    @abstractmethod
    def new_facade(self, folder_names: Sequence[str]) -> 'ArchiveDirectory':
        pass

    @abstractmethod
    def with_name(self, folder_name: str) -> 'ArchiveDirectory':
        pass

    @abstractmethod
    def exchange_contents(self, other: 'ArchiveDirectory'):
        pass

    @abstractmethod
    def search_file_recursively(
            self,
            subdir: Union[str, PurePosixPath],
            rglob_pattern,
            ) -> Sequence[PurePath]:
        pass

    @abstractmethod
    def write_file(self, path_parts, contents: bytes) -> None:
        pass

    @abstractmethod
    def create_fake_file(self, path_parts: PurePosixPath, file_size: int) -> None:
        pass

    @abstractmethod
    def file_exists(self, subpath: str) -> bool:
        pass

    @abstractmethod
    def get_parent(self) -> str:
        pass

    @abstractmethod
    def unlink_file(self, path: PurePath) -> None:
        pass

    @abstractmethod
    def remove_dir(self) -> None:
        pass

    @abstractmethod
    def files_size_sum_bytes(self, extension: str) -> int:
        pass

    @abstractmethod
    def get_timezone(self) -> tzinfo:
        pass


class FakeArchiveDirectory(ArchiveDirectory):

    def __init__(self):
        self._files = []

    def new_facade(self, folder_names: Sequence[str]) -> 'FakeArchiveDirectory':
        pass

    def with_name(self, folder_names: str) -> 'FakeArchiveDirectory':
        pass

    def exchange_contents(self, other: 'ArchiveDirectory'):
        pass

    def search_file_recursively(
            self,
            subdir: Union[str, PurePosixPath],
            rglob_pattern,
            ) -> Sequence[PurePath]:
        return self._files

    def write_file(self, path_parts, contents: bytes) -> None:
        pass

    def create_fake_file(self, path_parts: PurePosixPath, file_size: int) -> None:
        self._files.append(path_parts)

    def file_exists(self, subpath: str) -> bool:
        pass

    def get_parent(self) -> str:
        pass

    def unlink_file(self, path: PurePath) -> None:
        pass

    def remove_dir(self) -> None:
        pass

    def files_size_sum_bytes(self, extension: str) -> int:
        pass

    def get_timezone(self) -> tzinfo:
        pass
