# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import os
import re
import socket
import subprocess
import time
from collections import Counter
from typing import Optional

from config import global_config
from directories import NotALocalArtifact
from directories import make_artifact_store


class _DistributionGroup:

    def __init__(self, distribution_group: str):
        group = distribution_group
        groups = group.split(',') if group else []
        hosts = []
        for g in groups:
            m = re.search(r'\{(\d+)\.\.(\d+)\}', g)
            if m is None:
                hosts.append(g)
                continue
            [prefix, _] = g.split('{')
            [_, suffix] = g.split('}')
            [first, last] = m.groups()
            if first.startswith('0'):
                digit_count = len(first)
            else:
                digit_count = 0
            hosts.extend([
                prefix + f'{i:0{digit_count}d}' + suffix
                for i in range(int(first), int(last) + 1)
                ])
        self._hosts = hosts


class DefaultDistributionGroup(_DistributionGroup):
    """Distribution group sepcified in global config.

    >>> from config import global_config
    >>> global_config['distribution_group'] = 'sc-ft001'
    >>> DefaultDistributionGroup()._hosts
    ['sc-ft001']
    >>> global_config['distribution_group'] = 'a-001.b,a-{008..012}.b,a-015.b'
    >>> DefaultDistributionGroup()._hosts
    ['a-001.b', 'a-008.b', 'a-009.b', 'a-010.b', 'a-011.b', 'a-012.b', 'a-015.b']
    >>> global_config['distribution_group'] = ''
    >>> DefaultDistributionGroup()._hosts
    []
    >>> global_config['distribution_group'] = None
    >>> DefaultDistributionGroup()._hosts
    []
    """

    def __init__(self):
        super().__init__(global_config.get('distribution_group'))
        self._artifact_store = make_artifact_store()

    def share_file(self, source_uri: str, target_dir: str):
        if not self._hosts:
            _logger.info("Distribution group is empty, will not distribute %s", source_uri)
            return
        try:
            origin_file = self._artifact_store.get_local_path(source_uri)
        except NotALocalArtifact:
            raise RuntimeError(f"Cannot distribute non-local file {source_uri}")
        sources = [_RemotePath(socket.gethostname(), str(origin_file))]
        queued_targets = [
            _RemotePath(h, os.path.join(target_dir, origin_file.name)) for h in self._hosts]
        failed_targets = []
        started_at = time.monotonic()
        timeout_sec = 1200
        attempt_counter = Counter()
        while True:
            processes = []
            while sources and queued_targets:
                processes.append(_CopyProcess(sources.pop(), queued_targets.pop()))
            for process in processes:
                exit_code = process.wait()
                sources.append(process.source())
                if exit_code == 0:
                    sources.append(process.target())
                elif attempt_counter[process.target()] < 2:
                    attempt_counter[process.target()] += 1
                    queued_targets.append(process.target())
                else:
                    failed_targets.append(process.target())
            if not queued_targets:
                break
            if time.monotonic() - started_at > timeout_sec:
                raise RuntimeError(
                    f"Distribute process is not finished after {timeout_sec} seconds")
        if failed_targets:
            _logger.info("Failed to distribute file to %s", failed_targets)


class _RemotePath:

    def __init__(self, host: str, path: str):
        self._host = host
        self._path = path
        self._permissions = 'u=rw,go=r'

    def __repr__(self):
        return f'_RemotePath({self._host!r}, {self._path!r})'

    def push(self, other: '_RemotePath') -> subprocess.Popen:
        _logger.info("Push file: source=%s destination=%s", self, other)
        return subprocess.Popen([
            # Rsync cannot directly copy files between two remote hosts.
            # Use SSH to execute rsync push on target.
            'ssh', '-oBatchMode=yes', self._host,
            'rsync',
            '--mkpath',
            '--chmod', self._permissions,
            self._path, f'{other._host}:{other._path}',
            ])


class _CopyProcess:

    def __init__(self, source: _RemotePath, target: _RemotePath):
        self._source = source
        self._target = target
        self._process = source.push(target)

    def source(self) -> '_RemotePath':
        return self._source

    def target(self) -> '_RemotePath':
        return self._target

    def wait(self) -> Optional[int]:
        _logger.info("Waiting for %s to finish", self._process.args)
        try:
            exit_code = self._process.wait(360)
        except TimeoutError:
            try:
                self._process.kill()
            except OSError:
                pass
            try:
                exit_code = self._process.wait(10)
            except TimeoutError:
                _logger.warning("Failed to kill %s", self._process)
                exit_code = None
        return exit_code


_logger = logging.getLogger(__name__)
