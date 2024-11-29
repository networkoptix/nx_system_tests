# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from _internal.service_registry import gui_prerequisite_store
from directories import get_run_dir
from gui.client_start import start_desktop_client
from gui.desktop_ui import scene_items
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.media_capturing import SavedImage
from gui.desktop_ui.scene_items import Scene
from gui.desktop_ui.scene_items import SceneItem
from gui.desktop_ui.scene_items import get_screen_object
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.prerequisite_upload import gui_prerequisite_supplier
from tests.base_test import VMSTest


class test_scene_items_can_be_rotated_by_using_item_button(VMSTest):
    """Scene items can be rotated by using item button and mouse.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1882

    Selection-Tag: 1882
    Selection-Tag: scene_items
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        client_installation = exit_stack.enter_context(machine_pool.create_and_setup_only_client())
        testkit_api = start_desktop_client(machine_pool.get_testkit_port(), client_installation)
        hid = HID(testkit_api)
        MainMenu(testkit_api, hid).activate_browse_local_files()
        image_path = gui_prerequisite_supplier.upload_to_remote('backgrounds/test_background.png', client_installation.os_access)
        Scene(testkit_api, hid).open_image_as_item(image_path)
        scene_item = SceneItem(testkit_api, hid, 'test_background.png')
        scene_item.rotate(-90)
        original_image = SavedImage(gui_prerequisite_store.fetch('backgrounds/test_background.png'))
        screen = get_screen_object(testkit_api).image_capture().crop_border(1)
        assert screen.is_similar_to(original_image.get_grayscale().rotate(-90))
        assert scene_items.check_toolbar_ok(testkit_api)
        scene_item.rotate(180)
        screen = get_screen_object(testkit_api).image_capture().crop_border(1)
        assert screen.is_similar_to(original_image.get_grayscale().rotate(90))
        assert scene_items.check_toolbar_ok(testkit_api)


if __name__ == '__main__':
    exit(test_scene_items_can_be_rotated_by_using_item_button().main())
