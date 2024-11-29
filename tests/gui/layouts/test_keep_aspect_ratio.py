# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.scene_items import Scene
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.prerequisite_upload import gui_prerequisite_supplier
from tests.base_test import VMSTest


class test_keep_aspect_ratio(VMSTest):
    """Keep aspect ratio.

    Set the background, verify Ratio is check by default, verify default values of width
    and height, check each parameter is changed by changing the other,
    unset Ratio, check parameters became independent, set Ratio and check values of width
    and height got default values.
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/898

    Selection-Tag: 898
    Selection-Tag: layouts
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        background_path = gui_prerequisite_supplier.upload_to_remote('backgrounds/test_background.png', client_installation.os_access)
        layout_settings = Scene(testkit_api, hid).open_layout_settings()
        layout_settings.select_background(background_path)
        time.sleep(.5)
        assert layout_settings.get_aspect_ratio_field().is_checked()
        assert layout_settings.get_width_field().get_text() == '39 cells'
        assert layout_settings.get_height_field().get_text() == '40 cells'
        layout_settings.get_width_field().type_text('50')
        assert layout_settings.get_height_field().get_text() == '50 cells'
        layout_settings.get_height_field().type_text('30')
        assert layout_settings.get_width_field().get_text() == '30 cells'
        layout_settings.get_aspect_ratio_field().set(False)
        layout_settings.get_width_field().type_text('60')
        assert layout_settings.get_height_field().get_text() == '30 cells'
        layout_settings.get_height_field().type_text('20')
        layout_settings.get_aspect_ratio_field().set(True)
        assert layout_settings.get_width_field().get_text() == '39 cells'
        assert layout_settings.get_height_field().get_text() == '40 cells'


if __name__ == '__main__':
    exit(test_keep_aspect_ratio().main())
