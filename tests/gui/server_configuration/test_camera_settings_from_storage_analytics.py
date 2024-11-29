# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MjpegRtspCameraServer
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.resource_tree import ResourceTree
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from tests.base_test import VMSTest


class test_camera_settings_from_storage_analytics(VMSTest):
    """Camera context menu.

    # https://networkoptix.testrail.net/index.php?/cases/view/6158

    Selection-Tag: 6158
    Selection-Tag: server_configuration
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        license_server = LocalLicenseServer()
        exit_stack.enter_context(license_server.serving())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        server_vm.allow_license_server_access(license_server.url())
        server_api = server_vm.api
        server_api.set_license_server(license_server.url())
        server_api.activate_license(license_server.generate({
            'QUANTITY2': 1,
            'BRAND2': server_api.get_brand(),
            }))
        rtsp_server = MjpegRtspCameraServer()
        [rtsp1] = add_cameras(server_vm, rtsp_server, indices=[0])
        server_api.start_recording(rtsp1.id)
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        exit_stack.enter_context(rtsp_server.async_serve())
        time.sleep(10)
        # Stop recording after short recording to force camera's appearance in Storage Analytics
        server_api.stop_recording(rtsp1.id)
        with ResourceTree(testkit_api, hid).get_server(server_api.get_server_name()).open_settings() as server_settings:
            server_settings.open_analytics_tab()
            camera_settings = server_settings.analytics_tab.open_camera_settings(0)
            camera_settings.wait_until_appears()
            camera_settings.close()


if __name__ == '__main__':
    exit(test_camera_settings_from_storage_analytics().main())
