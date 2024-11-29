# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import os
import random
import subprocess
import time
from collections import Counter
from pathlib import Path


def main():
    ft_repo = str(Path('~ft/git_mirror/ft.git').expanduser())
    ft_local_repo = str(Path('~ft/git_mirror_local/ft.git').expanduser())
    if os.getenv('DRY_RUN'):
        _logger.info("Dry run: Would update repository to match remote")
        return 0
    for attempt in range(1, 101):
        fetch_command = ['git', '-C', ft_repo, 'remote', 'update']
        _logger.info("Updating repo %s, attempt number %d", ft_repo, attempt)
        try:
            process = subprocess.run(fetch_command, timeout=60)
        except subprocess.TimeoutExpired:
            _logger.info("Command %s timed out, retry", fetch_command)
            continue
        if process.returncode == 0:
            break
        sleep_sec = 3 + random.random() * 3
        _logger.info(
            "Fetch failed: exit code %s, retry after %.1f seconds",
            process.returncode, sleep_sec)
        time.sleep(sleep_sec)
    else:
        return 10
    subprocess.run(['mkdir', '-p', ft_local_repo], check=True)
    subprocess.run(['git', '-C', ft_local_repo, 'init', '--bare', '-q'], check=True)
    for attempt in range(1, 101):
        fetch_command = ['git', '-C', ft_local_repo, 'fetch', 'git@gitlab.nxvms.dev:ft/ft.git', '+refs/*:refs/remotes/origin/*']
        _logger.info("Updating repo %s, attempt number %d", ft_local_repo, attempt)
        try:
            process = subprocess.run(fetch_command, timeout=60)
        except subprocess.TimeoutExpired:
            _logger.info("Command %s timed out, retry", fetch_command)
            continue
        if process.returncode == 0:
            break
        sleep_sec = 3 + random.random() * 3
        _logger.info(
            "Fetch failed: exit code %s, retry after %.1f seconds",
            process.returncode, sleep_sec)
        time.sleep(sleep_sec)
    else:
        return 10
    hosts = [
        'beg-ft001',
        'beg-ft002',
        'sc-ft002',
        'sc-ft004',
        'sc-ft005',
        'sc-ft006',
        'sc-ft007',
        'sc-ft008',
        'sc-ft009',
        'sc-ft010',
        'sc-ft011',
        'sc-ft012',
        'sc-ft013',
        'sc-ft014',
        'sc-ft015',
        'sc-ft016',
        'sc-ft018',
        'sc-ft019',
        'sc-ft020',
        'sc-ft021',
        'sc-ft022',
        'sc-ft023',
        'sc-ft024',
        ]
    _wait_processes_to_finish([
        subprocess.Popen(['ssh', '-oBatchMode=yes', host, 'mkdir', '-p', ft_local_repo])
        for host in hosts
        ])
    _wait_processes_to_finish([
        subprocess.Popen(['ssh', '-oBatchMode=yes', host, 'git', '-C', ft_local_repo, 'init', '--bare', '-q'])
        for host in hosts
        ])
    _wait_processes_to_finish([
        subprocess.Popen(['git', '-C', ft_local_repo, 'push', f'git+ssh://{host}{ft_local_repo}', '+refs/remotes/origin/*:refs/*'])
        for host in hosts
        ])
    # Master repository should be updated latest to avoid inconsistency
    process = subprocess.run([
        'git',
        '-C', ft_local_repo,
        'push',
        '.',
        '+refs/remotes/origin/*:refs/*',
        ])
    if process.returncode != 0:
        _logger.error("Local push failed: %s", process)
        return 10
    else:
        return 0


def _wait_processes_to_finish(processes: list[subprocess.Popen]):
    max_attempts = 10
    attempt_counter = Counter()
    while processes:
        process = processes.pop()
        exit_code = process.wait()
        if exit_code == 0:
            continue
        elif attempt_counter[tuple(process.args)] < max_attempts:
            attempt_counter[tuple(process.args)] += 1
            _logger.warning(f"{process.args} failed with {exit_code=}; retry {attempt_counter[tuple(process.args)]}")
            time.sleep(1)
            processes.append(subprocess.Popen(process.args))
        else:
            raise RuntimeError(f"Failed {process.args} with {exit_code=}")


_logger = logging.getLogger(__name__)

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    exit(main())
