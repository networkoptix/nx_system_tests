# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from _internal.service_registry import gui_prerequisite_store
from directories import get_run_dir
from distrib import BranchNotSupported
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MjpegRtspCameraServer
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.media_capturing import SavedImage
from gui.desktop_ui.resource_tree import ResourceTree
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from tests.base_test import VMSTest


class test_licenses_calculation(VMSTest):
    """Licenses calculation.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/960

    Selection-Tag: 960
    Selection-Tag: camera_management
    """

    def _run(self, args, exit_stack):
        distrib_url = args.distrib_url
        installer_supplier = ClassicInstallerSupplier(distrib_url)
        if installer_supplier.distrib().newer_than('vms_6.0'):
            raise BranchNotSupported("Test should be fixed for VMS 6.1+")

        machine_pool = GuiTestStand(installer_supplier, get_run_dir())
        license_server = LocalLicenseServer()
        exit_stack.enter_context(license_server.serving())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        server_vm.allow_license_server_access(license_server.url())
        server_vm.api.set_license_server(license_server.url())
        rtsp_server = MjpegRtspCameraServer()
        [rtsp1, rtsp2, rtsp3] = add_cameras(server_vm, rtsp_server, indices=[0, 1, 2])
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        exit_stack.enter_context(rtsp_server.async_serve())
        server_vm.api.activate_license(license_server.generate({
            'QUANTITY2': 2,
            'BRAND2': server_vm.api.get_brand(),
            }))
        ResourceTree(testkit_api, hid).wait_for_cameras([rtsp1.name, rtsp2.name, rtsp3.name])
        camera_settings_dialog_1 = ResourceTree(testkit_api, hid).get_camera(rtsp1.name).open_settings()
        camera_settings_dialog_1.enable_recording()
        cameras = ResourceTree(testkit_api, hid).select_cameras([rtsp2.name, rtsp3.name])
        with cameras.open_settings_multiple_cameras() as camera_settings:
            camera_settings.activate_tab('Recording'.title())
            camera_settings.recording_tab.ensure_cannot_be_enabled()
            assert camera_settings.recording_tab.has_license_message('1 Professional License is required')
        cameras = ResourceTree(testkit_api, hid).select_cameras([rtsp1.name, rtsp2.name])
        with cameras.open_settings_multiple_cameras() as camera_settings:
            camera_settings.activate_tab('Recording'.title())
            current_toggle = camera_settings.recording_tab.get_enable_recording_checkbox().image_capture()
            path = gui_prerequisite_store.fetch('gui_elements/recording_toggle_intermediate.png')
            assert current_toggle.is_similar_to(SavedImage(path), correlation=0.95)
            camera_settings.recording_tab.toggle_recording_checkbox()
        rtree = ResourceTree(testkit_api, hid)
        # TODO: Need to fix in VMS 6.1+
        assert rtree.get_camera(rtsp1.name).is_recording()
        assert rtree.get_camera(rtsp2.name).is_recording()


if __name__ == '__main__':
    exit(test_licenses_calculation().main())
