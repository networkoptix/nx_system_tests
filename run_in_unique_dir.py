# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import getpass
import os
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Sequence


def main(args: Sequence[str]) -> int:
    directories_per_user = 5
    for i in range(1, directories_per_user + 1):
        lock_file = Path(f'unique-dir-{i:02d}.lock')
        lock_file.touch()
        lock = open(lock_file, mode='rb')
        if try_lock_exclusively(lock.fileno()):
            unique_dir = lock_file.with_suffix('')
            unique_dir.mkdir(exist_ok=True)
            print(f"{unique_dir} directory is locked for a run", flush=True)
            log_path = _get_log_path(unique_dir)
            log_url = 'http://{hostname}/~{username}/{relative_path}'.format(
                hostname=socket.gethostname(),
                username=getpass.getuser(),
                relative_path=Path(log_path).absolute().relative_to(Path.home()).as_posix(),
                )
            with open(log_path, mode='wb') as stderr_output:
                print(f'Log URL: {log_url}', flush=True)
                process = subprocess.run(
                    [sys.executable, *args],
                    cwd=str(unique_dir),
                    stderr=stderr_output.fileno(),
                    check=False,
                    )
            lock.close()
            return process.returncode
    else:
        print(f"Parallel job run quota for user {getpass.getuser()!r} exceeded. Please try again later", flush=True)
        return 20


def _get_log_path(unique_dir: Path) -> Path:
    suffix = '.log'
    log_files = [*unique_dir.glob(f'*{suffix}')]
    if len(log_files) >= 20:
        [oldest, *_] = sorted(log_files)
        oldest.unlink(missing_ok=True)
    return unique_dir.joinpath(f'run-{datetime.utcnow():%Y%m%d%H%M%S%f}{suffix}')


if os.name == 'nt':
    from ctypes import windll
    from ctypes.wintypes import HANDLE
    from ctypes.wintypes import DWORD
    from ctypes.wintypes import BOOL
    from msvcrt import get_osfhandle

    windll.kernel32.LockFile.argtypes = HANDLE, DWORD, DWORD, DWORD, DWORD
    windll.kernel32.LockFile.restype = BOOL

    def try_lock_exclusively(fileno: int) -> bool:
        return windll.kernel32.LockFile(get_osfhandle(fileno), 1, 0, 1, 0)

else:
    import fcntl

    def try_lock_exclusively(fileno: int) -> bool:
        try:
            fcntl.flock(fileno, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as err:
            if err.errno == 11:
                return False
            raise
        return True


if __name__ == '__main__':
    exit(main(sys.argv[1:]))
