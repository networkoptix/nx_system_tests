# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from directories import get_run_dir
from gui.client_start import start_desktop_client
from gui.desktop_ui.main_window import MainWindow
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from installation import WindowsClientInstallation
from tests.base_test import VMSTest


class test_check_correct_closing(VMSTest):
    """Checking correct closing.

    Jira: https://networkoptix.atlassian.net/browse/FT-2419

    Selection-Tag: base_functions
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        client_installation = exit_stack.enter_context(machine_pool.create_and_setup_only_client())
        testkit_api = start_desktop_client(machine_pool.get_testkit_port(), client_installation)
        hid = HID(testkit_api)
        MainWindow(testkit_api, hid).close_client_by_cross()
        _wait_client_stopped(client_installation)
        assert not client_installation.list_core_dumps(), 'Desktop Client crashed during closing'


def _wait_client_stopped(client_installation: WindowsClientInstallation):
    # Client may hang for some time if it crashes and is writing a core dump.
    finished_at = time.monotonic() + 5
    while True:
        if not client_installation.is_running():
            break
        if time.monotonic() > finished_at:
            raise RuntimeError('Desktop Client is still running')
        time.sleep(0.5)


if __name__ == '__main__':
    exit(test_check_correct_closing().main())
