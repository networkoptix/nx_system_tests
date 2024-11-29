# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
"""FT cleanup script.

Test produces and downloads many artifacts which consume common disk space.
Store artifacts in single location and cleanup them in a uniform way to
maintain free disk space on servers.

Specific cleanup functions are called from test run and spawns a process
if cleanup is required.
Cleanup is performed periodically to avoid unnecessary IO loads.
Only one process should become a leader and perform cleanup to avoid
unnecessary IO loads.
"""
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Sequence

from config import global_config
from directories._cleanup_strategy import CleanupStrategy
from directories._directories import CannotDeleteEntry
from directories._directories import Entry
from directories._directories import EntryRoot
from directories._directories import get_ft_artifacts_root
from directories._directories import get_ft_snapshots_cache_root
from directories._directories import get_ft_snapshots_origin_root
from directories._directories import list_entries
from directories._rate_limit import NotALeader
from directories._rate_limit import TimestampFileRateLimit


def main(args: Sequence[str]):
    [timestamp_file, target_size_gb, *directories] = args
    rate_limit = TimestampFileRateLimit(Path(timestamp_file))
    try:
        last_cleanup_at = rate_limit.become_leader()
    except NotALeader:
        return 0
    _logger.info(
        "Cleanup process started; last cleanup was at %s; "
        "will maintain %d GB of occupied space for %s",
        datetime.fromtimestamp(last_cleanup_at).isoformat(timespec='minutes'), int(target_size_gb), directories)
    target_size = int(target_size_gb) * 1024 * 1024 * 1024
    cleanup_strategy = GradualCleanup(
        target_size,
        last_cleanup_at,
        OldestFilesFirst([Path(d) for d in directories]),
        )
    cleanup_strategy.delete_least_significant()
    _logger.info("Clean up process finished")
    return 0


def clean_up_artifacts():
    _clean_up(
        Path('~/.cache/artifacts_cleanup_launched_at.txt').expanduser(),
        int(global_config['artifacts_size_limit_gb']),
        get_ft_artifacts_root(),
        Path('~/.cache/nx-func-tests-work-dir').expanduser(),
        Path('~/.cache/task_artifacts').expanduser(),
        Path('~/.cache/nx-func-tests/vms-installers').expanduser(),
        )


def clean_up_snapshots():
    if global_config.get('snapshots_origin_size_limit_gb') is not None:
        _clean_up(
            Path('~/.cache/snapshots_origin_cleanup_launched_at.txt').expanduser(),
            int(global_config['snapshots_origin_size_limit_gb']),
            get_ft_snapshots_origin_root(),
            Path('~/.cache/nxft-snapshots/').expanduser(),
            )
    if global_config.get('snapshots_cache_size_limit_gb') is not None:
        _clean_up(
            Path('~/.cache/snapshots_cache_cleanup_launched_at.txt').expanduser(),
            int(global_config['snapshots_cache_size_limit_gb']),
            get_ft_snapshots_cache_root(),
            Path('~/.cache/nxft-snapshots/').expanduser(),
            Path('~/.cache/nx-func-tests/vm-templates/').expanduser(),
            )


def _clean_up(timestamp_file: Path, target_size_gb: int, *target_directories: Path):
    """Spawn clean up process from other scripts.

    Cleanup is not a central activity. No need to wait for it.
    Use os.spawn*() as subprocess.Popen() produces a warning
    in __del__() if forgotten.
    """
    if not TimestampFileRateLimit(timestamp_file).run_is_allowed():
        _logger.info("Cleanup launched recently; cleanup not required yet, exit")
        return
    script_args = [
        str(timestamp_file),
        str(target_size_gb),
        *[str(d) for d in target_directories],
        ]
    _logger.info("Start clean up process; args: %s", script_args)
    os.spawnl(
        os.P_NOWAITO,
        sys.executable,
        'python3',
        '-m', __name__,
        *script_args,
        )


class GradualCleanup(CleanupStrategy):

    def delete_least_significant(self):
        entries_before_cleanup = self._entry_root.list_entries()
        total_size_before_cleanup = sum(e.size() for e in entries_before_cleanup)
        space_to_cleanup = self._get_space_size_to_cleanup(entries_before_cleanup)
        _logger.info(
            "Occupied space before cleanup: %s. Attempt to free at least %s",
            _human_readable_size(total_size_before_cleanup), _human_readable_size(space_to_cleanup))
        for entry in entries_before_cleanup:
            if space_to_cleanup <= 0:
                break
            try:
                entry.delete()
            except CannotDeleteEntry as e:
                _logger.debug(e)
            else:
                space_to_cleanup -= entry.size()
        entries_after_cleanup = self._entry_root.list_entries()
        total_size_after_cleanup = sum(e.size() for e in entries_after_cleanup)
        _logger.info(
            "Occupied space after cleanup: %s", _human_readable_size(total_size_after_cleanup))

    def _get_space_size_to_cleanup(self, entries: Sequence[Entry]) -> int:
        # Free a bit more space than was taken from the last cleanup.
        # This means that the pace of the cleanup is proportional to the pace
        # of generating new artifacts. If something starts to generate
        # artifacts at an unexpectedly quick pace, the cleanup pace will
        # increase proportionally. If the target size is manually reconfigured
        # to be much lower, older artifacts will be removed gradually,
        # limited by the same proportional pace.
        taken_since_last_cleanup = sum(
            e.size()
            for e in entries
            if e.modified_at() > self._last_cleanup_at
            )
        excess = max(0, sum(e.size() for e in entries) - self._target_size)
        _logger.debug(
            "Occupied space since last cleanup: %s; excess: %s",
            _human_readable_size(taken_since_last_cleanup), _human_readable_size(excess))
        return min(int(taken_since_last_cleanup * 1.5), excess)


class OldestFilesFirst(EntryRoot):

    def list_entries(self):
        return sorted(
            [e for d in self._root_directories for e in list_entries(d)],
            key=lambda e: e.used_at(),
            )


def _human_readable_size(size: int) -> str:
    for unit in ('', 'K', 'M', 'G', 'T'):
        formatted_size = f"{size:.1f} {unit}Bytes"
        if size < 1024:
            break
        size /= 1024
    return formatted_size


_logger = logging.getLogger(__name__)


if __name__ == '__main__':
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    file_handler = logging.handlers.RotatingFileHandler(
        Path('~/.cache').expanduser() / 'cache_cleanup.log', maxBytes=200 * 1024**2, backupCount=1)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(process)d %(name)s %(levelname)s %(message)s'))
    file_handler.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    exit(main(sys.argv[1:]))
