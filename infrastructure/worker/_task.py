# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import os
import subprocess
import sys
import time
from contextlib import ExitStack
from contextlib import contextmanager
from pathlib import Path
from typing import Generator
from typing import Mapping
from typing import Protocol
from typing import Sequence

_logger = logging.getLogger(__name__)


class LocalTask:

    def __init__(
            self,
            script: str,
            args: Sequence[str],
            env: Mapping[str, str],
            ):
        self._script = script
        self._args = args
        self._env = {**os.environ, **env}

    def run(
            self,
            run_dir: Path,
            task_artifacts_root: Path,
            timeout_sec: float,
            ) -> Generator[bytes, None, str]:
        _logger.info("args=%s cwd=%s env=%s", self._args, run_dir, self._env)
        [python, *args] = self._args
        if python != 'python3':
            _logger.warning("Non-python scripts are not supported")
            return 'failed_not_a_python_command'
        with ExitStack() as es:
            console = es.enter_context(self._console(task_artifacts_root))
            console.log(f"Run args={self._args} cwd={run_dir}")
            stdout_file = task_artifacts_root / 'stdout.txt'
            with open(stdout_file, mode='wb') as stdout_output:
                # Opened file descriptor for stdout file is inherited by the child process.
                # Keeping it in this process is unnecessary.
                process = subprocess.Popen(
                    [sys.executable, *self._args[1:]],
                    cwd=run_dir,
                    stdin=subprocess.PIPE,
                    stdout=stdout_output.fileno(),
                    stderr=console.fileno(),
                    env=self._env,
                    )
            input_bytes = self._script.encode('utf8')
            written_size = process.stdin.write(input_bytes)
            assert written_size == len(input_bytes)
            process.stdin.close()
            stdout_input = es.enter_context(open(stdout_file, mode='rb'))
            started_at = time.monotonic()
            while True:
                try:
                    exit_code = process.wait(1)
                except subprocess.TimeoutExpired:
                    _logger.debug("Process pid=%d still running", process.pid)
                    exit_code = None
                stdout = stdout_input.read()
                if stdout:
                    yield stdout
                if exit_code is not None:
                    _logger.info("Script finished with exit code %d", exit_code)
                    console.log(f"Command finished with {exit_code=}")
                    task_status = 'succeed' if exit_code == 0 else f'failed_with_code_{exit_code}'
                    break
                elif time.monotonic() - started_at > timeout_sec:
                    task_status = 'failed_timed_out'
                    process.kill()
                    # Avoid ResourceWarning from subprocess that process is still running,
                    # give it a chance to terminate.
                    try:
                        process.wait(10)
                    except subprocess.TimeoutExpired:
                        _logger.warning("Process pid=%d is running after kill", process.pid)
                    break
            return task_status

    @contextmanager
    def _console(self, task_artifacts_root: Path):
        task_artifacts_root.mkdir(exist_ok=True)
        console_log_path = task_artifacts_root / 'console.log'
        with console_log_path.open(mode='wb') as log_file:
            yield _Console(log_file)


class _Console:

    def __init__(self, buffer: '_ConsoleBuffer'):
        self._buffer = buffer

    def log(self, message: str):
        self._buffer.write(message.encode('ascii') + b'\n')
        self._buffer.flush()

    def fileno(self) -> int:
        return self._buffer.fileno()


class _ConsoleBuffer(Protocol):

    def fileno(self) -> int:
        ...

    def write(self, message: bytes, /) -> int:
        ...

    def flush(self):
        ...
