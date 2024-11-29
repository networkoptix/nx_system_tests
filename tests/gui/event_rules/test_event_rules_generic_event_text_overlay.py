# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import time

from directories import get_run_dir
from distrib import BranchNotSupported
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.media_capturing import ImagePiecePercentage
from gui.desktop_ui.ocr import ImageTextRecognition
from gui.desktop_ui.ocr import TextNotFound
from gui.desktop_ui.resource_tree import ResourceTree
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import similar_playing_testcameras
from tests.base_test import VMSTest


class test_event_rules_generic_event_text_overlay(VMSTest):
    """Event rules generic event shows text overlay for fixed duration.

    Add 2 cameras, add generic event show text overlay on camera1 and also show on source camera.
    Trigger generic event on camera2. Check correct text is displayed on both cameras only for fixed duration.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/124
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/137

    Selection-Tag: 124
    Selection-Tag: 137
    Selection-Tag: event_rules
    """

    def _run(self, args, exit_stack):
        distrib_url = args.distrib_url
        installer_supplier = ClassicInstallerSupplier(distrib_url)
        if installer_supplier.distrib().newer_than('vms_6.0'):
            raise BranchNotSupported("Test should be fixed for VMS 6.1+")

        machine_pool = GuiTestStand(installer_supplier, get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        # same video for multiple cameras
        exit_stack.enter_context(similar_playing_testcameras(machine_pool, server_vm.os_access, 'samples/overlay_test_video.mp4', 2))
        [test_camera_1, test_camera_2] = server_vm.api.add_test_cameras(0, 2)

        server_vm.api.start_recording(test_camera_1.id, test_camera_2.id)

        system_administration_dialog = MainMenu(testkit_api, hid).activate_system_administration()
        event_rules_window = system_administration_dialog.open_event_rules()
        rule_dialog = event_rules_window.get_add_rule_dialog()
        rule_dialog.get_generic_event()
        action_gui = rule_dialog.get_text_overlay_action()
        action_gui.set_cameras([test_camera_1.name])
        # TODO: Need to fix in VMS 6.1+
        action_gui.get_use_source_camera_checkbox().set(True)
        action_gui.get_overlay_duration_box().type_text('30')
        rule_dialog.save_and_close()
        event_rules_window.close()
        system_administration_dialog.save_and_close()

        rtree = ResourceTree(testkit_api, hid)
        camera_1_scene_item = rtree.get_camera(test_camera_1.name).open()
        rtree.get_camera(test_camera_2.name).open()
        metadata = json.dumps({'cameraRefs': [str(test_camera_2.id)]})
        server_vm.api.create_event(source='device1', caption='text', description='description', metadata=metadata)
        time.sleep(2)
        assert _has_expected_text_on_scene(camera_1_scene_item)
        assert _has_expected_text_on_scene(camera_1_scene_item)

        # Checking camera scene items text takes about 2-3 seconds.
        # We take additional 2-3 seconds for more stable check.
        # Total wait is about 20 seconds (as test requires).
        time.sleep(15)
        assert _has_expected_text_on_scene(camera_1_scene_item)
        assert _has_expected_text_on_scene(camera_1_scene_item)

        time.sleep(15)
        assert _no_expected_text_on_scene(camera_1_scene_item)
        assert _no_expected_text_on_scene(camera_1_scene_item)


def _has_expected_text_on_scene(camera_item):
    expected_texts = ['text', 'description']
    try:
        _recognize(camera_item).multiple_line_indexes(expected_texts)
    except TextNotFound:
        return False
    return True


def _no_expected_text_on_scene(camera_item):
    missed_texts = ['text', 'description']
    recognition_result = _recognize(camera_item)
    for text in missed_texts:
        try:
            recognition_result.line_index(text)
            return False
        except TextNotFound:
            pass
    return True


def _recognize(camera_item):
    screen = camera_item.image_capture()
    cropped_screen = screen.crop_percentage(ImagePiecePercentage(0.6, 0.6, 0.4, 0.4))
    return ImageTextRecognition(cropped_screen)


if __name__ == '__main__':
    exit(test_event_rules_generic_event_text_overlay().main())
