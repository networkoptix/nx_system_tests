# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from datetime import timedelta

from directories import get_run_dir
from gui.client_start import start_desktop_client
from gui.desktop_ui.audit_trail import AuditTrail
from gui.desktop_ui.audit_trail import AuditTrailSessionsTable
from gui.desktop_ui.dialogs.connect_to_server import first_time_connect
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.messages import MessageBox
from gui.gui_test_stand import GuiTestStand
from gui.server_login_steps import _log_in_to_server
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_adding_user_sessions(VMSTest):
    """Adding user sessions.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/2039
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/2040

    Selection-Tag: 2039
    Selection-Tag: 2040
    Selection-Tag: audit_trail
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        testkit_api = start_desktop_client(machine_pool.get_testkit_port(), client_installation)
        hid = HID(testkit_api)
        connect_dialog = MainMenu(testkit_api, hid).activate_connect_to_server()
        address, port = machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm)
        connect_dialog.connect(address, 'admin', 'wrong_password', port)
        first_time_connect(testkit_api, hid)
        MessageBox(testkit_api, hid).close_by_button('OK')
        connect_dialog.cancel()
        address_port = machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm)
        _log_in_to_server(testkit_api, hid, address_port, server_vm)
        AuditTrail.open(testkit_api, hid)
        sessions_table = AuditTrailSessionsTable(testkit_api, hid)
        assert sessions_table.session_ends(1) == 'Unsuccessful login'
        assert sessions_table.user(0) == 'admin'
        assert sessions_table.activity(0) == '1 action'
        assert sessions_table.session_ends(0) == ''
        assert sessions_table.duration(0) == ''
        tolerance = timedelta(minutes=2)
        naive_session_begins = sessions_table.session_begins(0)
        # VMS 6.0.
        server_dt = server_vm.os_access.get_datetime()
        session_begins_server_tz = naive_session_begins.replace(tzinfo=server_dt.tzinfo)
        # VMS 6.1 and higher.
        client_dt = client_installation.os_access.get_datetime()
        session_begins_client_tz = naive_session_begins.replace(tzinfo=client_dt.tzinfo)
        # TODO: Make check stricter https://networkoptix.atlassian.net/browse/FT-2568
        assert any([
            abs(session_begins_server_tz - server_dt) < tolerance,
            abs(session_begins_client_tz - client_dt) < tolerance,
            ])
        assert sessions_table.ip(0) == client_installation.os_access.source_address()


if __name__ == '__main__':
    exit(test_adding_user_sessions().main())
