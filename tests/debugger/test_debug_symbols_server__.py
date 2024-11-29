# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from contextlib import ExitStack

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import Mediaserver
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from os_access import PosixAccess
from os_access import RemotePath
from os_access import WindowsAccess


def _test_debug_symbols_server(distrib_url, vm_type: str, exit_stack: ExitStack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), 'v0')
    mediaserver_stand = exit_stack.enter_context(pool.one_mediaserver(vm_type))
    mediaserver = mediaserver_stand.mediaserver()
    os_access = mediaserver_stand.os_access()
    mediaserver.start()
    mediaserver.api.setup_local_system()
    pid = mediaserver.service.status().pid
    os_access.traffic_capture.stop()  # Otherwise, GDB could be killed by OOM in Linux.
    mediaserver.take_backtrace('test_debug_symbols')
    [backtrace_file] = [f for f in mediaserver.list_backtraces() if 'test_debug_symbols' in f.name]
    backtrace = backtrace_file.read_bytes()
    assert b'MediaServerProcess::main' in backtrace, 'Failed to take a backtrace'
    backtrace_file.unlink()  # The new parsed backtrace file will be created during the teardown process.
    core_file_dir = os_access.tmp() / 'core'
    core_file_dir.mkdir()
    _dump_mediaserver_process(mediaserver, core_file_dir)
    [core_file] = core_file_dir.glob('*.dmp')
    parsed_dump = mediaserver.parse_core_dump(core_file)
    parsed_dump_file = get_run_dir() / (core_file.name + '.backtrace.txt')
    parsed_dump_file.write_bytes(parsed_dump)
    assert b'MediaServerProcess::main' in parsed_dump, 'Failed to parse core dump'
    assert mediaserver.api.is_online()
    assert mediaserver.service.status().pid == pid, 'Mediaserver\'s PID was changed'


def _dump_mediaserver_process(mediaserver: Mediaserver, core_file_dir: RemotePath):
    if isinstance(mediaserver.os_access, WindowsAccess):
        result = mediaserver.os_access.run(
            [
                r'c:\sysinternals\procdump64.exe',
                '-accepteula',
                '-mm',
                mediaserver.get_binary_path().name,
                core_file_dir,
                ],
            check=False,  # procdump always returns a non-zero return code.
            )
        if result.returncode not in (0, 1):
            stderr = result.stderr.decode(errors='backslashreplace')
            raise RuntimeError(f'Failed to dump Mediaserver process: {stderr}')
    elif isinstance(mediaserver.os_access, PosixAccess):
        status = mediaserver.service.status()
        core_file = core_file_dir / 'mediaserver_core'
        mediaserver.os_access.shell.run(['gcore', '-o', core_file, status.pid], timeout_sec=90)
        [core_file, *_] = core_file_dir.glob('mediaserver_core.*')  # PID was added as a file extension.
        core_file_new_name = core_file_dir / (core_file.name + '.dmp')
        core_file.rename(core_file_new_name)
    else:
        raise RuntimeError('Unsupported OS')
