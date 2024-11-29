# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from _internal.service_registry import gui_prerequisite_store
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.video.ffprobe import extract_start_timestamp
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.timeline import Timeline
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from tests.base_test import VMSTest


class test_search_in_resource_tree(VMSTest):
    """Search in resource tree.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1916

    Selection-Tag: 1916
    Selection-Tag: resource_tree
    Selection-Tag: screenshots
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        license_server = LocalLicenseServer()
        exit_stack.enter_context(license_server.serving())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        server_vm.allow_license_server_access(license_server.url())
        server_vm.api.set_license_server(license_server.url())
        server_vm.api.activate_license(license_server.generate({
            'CLASS2': 'videowall',
            'QUANTITY2': 2,
            'BRAND2': server_vm.api.get_brand(),
            }))
        server_vm.api.add_videowall('Test video wall')
        server_vm.api.modify_web_page(server_vm.api.get_web_page_by_name('Support').id, 'Test web page')
        exit_stack.enter_context(playing_testcamera(machine_pool, server_vm.os_access, 'samples/time_test_video.mp4'))
        [test_camera_1] = server_vm.api.add_test_cameras(0, 1)
        server_vm.api.rename_camera(test_camera_1.id, 'Test camera')
        server_vm.api.rename_server('Test server')
        # For image and video create temporary ones if we rename here files used in other tests, they
        # will stuck renamed and this will break all tests depending on those files
        local_file_path = gui_prerequisite_store.fetch('upload/mp4.mp4')
        start_time = extract_start_timestamp(local_file_path)
        camera_id = server_vm.api.add_virtual_camera('VirtualCamera')
        with server_vm.api.virtual_camera_locked(camera_id) as token:
            server_vm.api.upload_to_virtual_camera(camera_id, local_file_path, token, start_time)
        testkit_api, camera_scene_item = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, 'VirtualCamera')
        hid = HID(testkit_api)
        save_screenshot_dialog = camera_scene_item.open_save_screenshot_dialog()
        save_screenshot_dialog.make_screenshot(client_installation.temp_dir() / 'Test image', 'PNG Image (*.png)')
        export_settings = Timeline(testkit_api, hid).open_export_video_dialog_for_interval(0, 0.9)
        export_settings.export_with_specific_path(client_installation.temp_dir() / 'Test video.mp4')
        # Create other stuff
        MainMenu(testkit_api, hid).activate_new_showreel()
        rtree = ResourceTree(testkit_api, hid)
        assert rtree.count_showreels() == 1
        rtree.get_showreel('Showreel').rename_using_context_menu('Test showreel')

        ResourceTree(testkit_api, hid).set_search('Test')
        rtree = ResourceTree(testkit_api, hid)
        assert rtree.has_server('Test server')
        assert rtree.has_camera('Test camera')
        assert rtree.has_layout('TestLayout')
        assert rtree.has_showreel('Test showreel')
        assert rtree.has_videowall('Test video wall')
        assert rtree.has_webpage('Test web page')
        assert rtree.has_local_file('Test image.png')
        assert rtree.has_local_file('Test video.mp4')
        assert not rtree.has_camera('VirtualCamera')

        camera = server_vm.api.get_camera_by_name('Test camera')
        ResourceTree(testkit_api, hid).set_search(camera._mac)
        rtree = ResourceTree(testkit_api, hid)
        assert rtree.has_server('Test server')
        assert rtree.has_camera('Test camera')
        assert not rtree.has_camera('VirtualCamera')
        assert not rtree.has_layout('Test layout')
        assert not rtree.has_showreel('Test showreel')
        assert not rtree.has_videowall('Test video wall')
        assert not rtree.has_webpage('Test web page')
        assert not rtree.has_local_file('Test image.png')
        assert not rtree.has_local_file('Test video.mp4')

        # No model for virtual nor testcamera.
        # Has to be added when different type of camera is used for test.

        camera1 = server_vm.api.get_camera_by_name('Test camera')
        ResourceTree(testkit_api, hid).set_search(camera1._vendor)
        rtree = ResourceTree(testkit_api, hid)
        assert rtree.has_server('Test server')
        assert rtree.has_camera('Test camera')
        # This webpage will also be shown because it contains NetworkOptix inside its url
        assert rtree.has_webpage('Test web page')
        assert not rtree.has_layout('Test layout')
        assert not rtree.has_showreel('Test showreel')
        assert not rtree.has_videowall('Test video wall')
        assert not rtree.has_local_file('Test image.png')
        assert not rtree.has_local_file('Test video.mp4')
        assert not rtree.has_camera('VirtualCamera')

        ResourceTree(testkit_api, hid).set_search('127.0')
        rtree = ResourceTree(testkit_api, hid)
        assert rtree.has_server('Test server')
        assert rtree.has_camera('Test camera')
        assert not rtree.has_layout('Test layout')
        assert not rtree.has_showreel('Test showreel')
        assert not rtree.has_videowall('Test video wall')
        assert not rtree.has_webpage('Test web page')
        assert not rtree.has_local_file('Test image.png')
        assert not rtree.has_local_file('Test video.mp4')
        assert not rtree.has_camera('VirtualCamera')


if __name__ == '__main__':
    exit(test_search_in_resource_tree().main())
