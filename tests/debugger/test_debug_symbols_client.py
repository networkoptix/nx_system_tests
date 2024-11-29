# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys

from directories import get_run_dir
from gui.client_start import start_desktop_client
from gui.gui_test_stand import GuiTestStand
from installation import ClassicInstallerSupplier
from runner.ft_test import run_ft_test
from tests.base_test import VMSTest


class test_debug_symbols_client(VMSTest):

    def _run(self, args, exit_stack):
        _test_debug_symbols_client(args.distrib_url, exit_stack)


def _test_debug_symbols_client(distrib_url, exit_stack):
    artifacts_dir = get_run_dir()
    machine_pool = GuiTestStand(ClassicInstallerSupplier(distrib_url), get_run_dir())
    client = exit_stack.enter_context(machine_pool.create_and_setup_only_client())
    start_desktop_client(machine_pool.get_testkit_port(), client)
    dumps_dir = client._local_app_data
    result = client.os_access.run(
        [r'c:\sysinternals\procdump64.exe', '-accepteula', '-mm', client.get_binary_path().name, dumps_dir],
        check=False,  # procdump always returns a non-zero return code.
        )
    if result.returncode not in (0, 1):
        stderr = result.stderr.decode(errors='backslashreplace')
        raise RuntimeError(f'Failed to dump Desktop Client process: {stderr}')
    client._parse_core_dumps(artifacts_dir)
    parsed_dump_file = next(artifacts_dir.glob('*.dmp.backtrace.txt'))
    parsed_dump = parsed_dump_file.read_bytes()
    assert b'nx_vms_client_desktop!nx::vms::client::desktop::runApplication' in parsed_dump, 'Failed to parse core dump'
    parsed_dump_file.unlink()  # The new parsed core dump will be created during the teardown process.
    client.take_backtrace(artifacts_dir)
    parsed_backtrace_file = next(artifacts_dir.glob('*HDWitness.exe.backtrace.txt'))
    backtrace = parsed_backtrace_file.read_bytes()
    assert b'nx_vms_client_desktop!nx::vms::client::desktop::runApplication' in backtrace, 'Failed to take a backtrace'
    parsed_backtrace_file.unlink()  # The new parsed backtrace file will be created during the teardown process.


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [
        test_debug_symbols_client(),
        ]))
