# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from distrib import BranchNotSupported
from doubles.http_server.http_server import create_test_http_server
from gui.client_start import start_client_with_web_page_open
from gui.gui_test_stand import GuiTestStand
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_open_tab_and_link_in_webpage(VMSTest):
    """Switching between tabs on web page.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/4606

    Selection-Tag: 4606
    Selection-Tag: webpages
    """

    def _run(self, args, exit_stack):
        distrib_url = args.distrib_url
        installer_supplier = ClassicInstallerSupplier(distrib_url)
        if installer_supplier.distrib().newer_than('vms_6.0'):
            raise BranchNotSupported("Test should be fixed for VMS 6.1+")

        machine_pool = GuiTestStand(installer_supplier, get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        test_http_server = create_test_http_server('page_with_tabs')
        exit_stack.enter_context(test_http_server)
        link = f'http://{client_installation.os_access.source_address()}:{test_http_server.server_port}'
        scene_item, _testkit_api, _hid = start_client_with_web_page_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            link,
            )
        # TODO: Need to fix in VMS 6.1+
        scene_item.click_on_phrase('Frog')
        scene_item.wait_for_phrase_exists('Kermit')
        scene_item.click_link('Dog')
        scene_item.wait_for_phrase_exists('Muhtar')


if __name__ == '__main__':
    exit(test_open_tab_and_link_in_webpage().main())
