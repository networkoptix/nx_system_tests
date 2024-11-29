# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.http_server.http_server import create_test_http_server
from gui.client_start import start_client_with_web_page_open
from gui.gui_test_stand import GuiTestStand
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_scrollbar_in_webpage_item(VMSTest):
    """Check scroll on web page.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/4608

    Selection-Tag: 4608
    Selection-Tag: webpages
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        test_http_server = create_test_http_server('scrollbar_page')
        exit_stack.enter_context(test_http_server)
        link = f'http://{client_installation.os_access.source_address()}:{test_http_server.server_port}'
        scroll_page, _testkit_api, hid = start_client_with_web_page_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            link,
            )
        scroll_page.wait_for_accessible()
        # Test vertical scroll
        scroll_page.wait_for_phrase_exists("Pear")
        scroll_page.scroll_to_phrase("Pear", "Banana")
        assert not scroll_page.has_phrase("Pear")
        # Test horizontal scroll
        assert scroll_page.has_phrase("Orange")
        assert not scroll_page.has_phrase("Pineapple")
        try:
            hid.keyboard_press('Shift')
            scroll_page.scroll_to_phrase("Orange", "Pineapple")
        finally:
            hid.keyboard_release('Shift')
        assert not scroll_page.has_phrase("Orange")


if __name__ == '__main__':
    exit(test_scrollbar_in_webpage_item().main())
