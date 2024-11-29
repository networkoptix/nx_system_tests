# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from _internal.service_registry import gui_prerequisite_store
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.video.vlc_player import VLCPlayer
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.media_capturing import SavedImage
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.timeline import Timeline
from gui.gui_test_stand import GuiTestStand
from gui.server_login_steps import _log_in_using_main_menu
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.prerequisite_upload import gui_prerequisite_supplier
from mediaserver_scenarios.testcamera_setup import testcameras_with_just_recorded_archive
from tests.base_test import VMSTest


class test_watermark_shown_in_vlc_player(VMSTest):
    """Video Watermarks protection by export as avi.

    # https://networkoptix.testrail.net/index.php?/cases/view/42976

    Selection-Tag: 42976
    Selection-Tag: watermarks_playback
    Selection-Tag: export
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        license_server = LocalLicenseServer()
        exit_stack.enter_context(license_server.serving())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        server_vm.allow_license_server_access(license_server.url())
        server_vm.api.set_license_server(license_server.url())
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        server_vm.api.activate_license(license_server.generate({
            'QUANTITY2': 2,
            'BRAND2': server_vm.api.get_brand(),
            }))
        MainMenu(testkit_api, hid).activate_system_administration().enable_watermark()
        server_vm.api.add_local_advanced_viewer('AV', 'WellKnownPassword2')
        [test_camera_1] = testcameras_with_just_recorded_archive(
            nx_server=server_vm, video_file='samples/test_video.mp4')
        address_port = machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm)
        _log_in_using_main_menu(testkit_api, hid, address_port, 'AV', 'WellKnownPassword2')
        ResourceTree(testkit_api, hid).get_camera(test_camera_1.name).open()
        export_settings = Timeline(testkit_api, hid).open_export_video_dialog_for_interval(0, 0.3)
        timestamp_feature = export_settings.make_timestamp_feature_active()
        timestamp_feature.set_size(30)
        export_settings.preview.set_timestamp_position('bottom_left')
        image_path = gui_prerequisite_supplier.upload_to_remote('samples/test_image_overlay.png', client_installation.os_access)
        image_feature = export_settings.make_image_feature_active()
        image_feature.set(str(image_path))
        export_settings.export_with_specific_path(client_installation.temp_dir() / '42976.avi')
        file = client_installation.temp_dir() / '42976.avi'
        snapshot_path = VLCPlayer(client_installation.os_access).get_preview(file)
        actual_file_path = get_run_dir() / 'snapshot.png'
        actual_file_path.write_bytes(snapshot_path.read_bytes())
        actual_image_capture = SavedImage(actual_file_path)
        expected_image_capture = SavedImage(gui_prerequisite_store.fetch('test42976/screen.png'))
        assert actual_image_capture.is_similar_to(expected_image_capture)


if __name__ == '__main__':
    exit(test_watermark_shown_in_vlc_player().main())
