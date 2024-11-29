# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.timeline import Timeline
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.prerequisite_upload import gui_prerequisite_supplier
from tests.base_test import VMSTest


class test_watermark_audio(VMSTest):
    """Success watermark for export with audio.

    Export mkv video for with audio, open exported video, check watermark is matched

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/20887

    Selection-Tag: 20887
    Selection-Tag: export
    Selection-Tag: watermarks_export
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
        remote_path = gui_prerequisite_supplier.upload_to_remote('localfiles/video_sound.mkv', client_installation.os_access)
        MainMenu(testkit_api, hid).open_local_settings_dialog().add_folder(remote_path.parent)
        ResourceTree(testkit_api, hid).wait_for_any_local_file()
        ResourceTree(testkit_api, hid).get_local_file('video_sound.mkv').open()
        export_settings = Timeline(testkit_api, hid).open_export_video_dialog_for_interval(0, 0.9)
        export_settings.export_with_specific_path(client_installation.temp_dir() / '20887.mkv')
        local_file_node = ResourceTree(testkit_api, hid).wait_for_local_file('20887.mkv')
        scene_item = local_file_node.open_in_new_tab()
        scene_item.wait_for_accessible()
        with scene_item.open_context_menu().open_check_watermark_dialog() as watermark_dialog:
            watermark_dialog.wait_for_matched()


if __name__ == '__main__':
    exit(test_watermark_audio().main())
