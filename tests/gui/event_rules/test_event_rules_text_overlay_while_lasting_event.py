# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import time

from directories import get_run_dir
from distrib import BranchNotSupported
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.media_capturing import ImagePiecePercentage
from gui.desktop_ui.ocr import ImageTextRecognition
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_api import EventState
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from tests.base_test import VMSTest


class test_event_rules_text_overlay_while_lasting_event(VMSTest):
    """Event rules generic event shows text overlay only for fixed duration.

    Add 2 cameras, add generic event show text overlay on camera1 and also show on source camera.
    Trigger generic event on camera2. Check correct text is displayed on both cameras only for fixed duration.
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/139

    Selection-Tag: 139
    Selection-Tag: event_rules
    """

    # TODO: This test has to check input event, not generic one. Has to be fixed.
    def _run(self, args, exit_stack):
        distrib_url = args.distrib_url
        installer_supplier = ClassicInstallerSupplier(distrib_url)
        if installer_supplier.distrib().newer_than('vms_6.0'):
            raise BranchNotSupported("Test should be fixed for VMS 6.1+")

        machine_pool = GuiTestStand(installer_supplier, get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        exit_stack.enter_context(playing_testcamera(machine_pool, server_vm.os_access, 'samples/overlay_test_video.mp4'))
        [test_camera_1] = server_vm.api.add_test_cameras(0, 1)
        testkit_api, camera_scene_item = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, test_camera_1.name)
        hid = HID(testkit_api)
        # same video for multiple cameras
        server_vm.api.start_recording(test_camera_1.id)
        system_administration_dialog = MainMenu(testkit_api, hid).activate_system_administration()
        event_rules_window = system_administration_dialog.open_event_rules()
        rule_dialog = event_rules_window.get_add_rule_dialog()
        rule_dialog.get_generic_event()
        action_gui = rule_dialog.get_text_overlay_action()
        action_gui.set_cameras([test_camera_1.name])
        # TODO: Need to fix in VMS 6.1+
        action_gui.get_display_text_for_checkbox().set(False)  # Non-actual option
        rule_dialog.save_and_close()
        event_rules_window.close()
        system_administration_dialog.save_and_close()

        metadata = json.dumps({'cameraRefs': [str(test_camera_1.id)]})
        server_vm.api.create_event(EventState.ACTIVE, source='device1', caption='text', description='description', metadata=metadata)
        time.sleep(2)
        assert _compare_text(camera_scene_item)

        time.sleep(10)
        assert _compare_text(camera_scene_item)

        server_vm.api.create_event(EventState.INACTIVE, source='device1')
        time.sleep(2)
        assert not _compare_text(camera_scene_item)


def _compare_text(camera_item):
    screen = camera_item.image_capture()
    cropped_screen = screen.crop_percentage(ImagePiecePercentage(0.6, 0.6, 0.4, 0.4))
    return ImageTextRecognition(cropped_screen).has_line('text')


if __name__ == '__main__':
    exit(test_event_rules_text_overlay_while_lasting_event().main())
