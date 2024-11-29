# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from datetime import datetime

from _internal.service_registry import gui_prerequisite_store
from directories import get_run_dir
from doubles.video.ffprobe import SampleMediaFile
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.layouts import LayoutTabBar
from gui.desktop_ui.media_capturing import SavedImage
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import Scene
from gui.desktop_ui.timeline import Timeline
from gui.desktop_ui.timeline import TimelineNavigation
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from tests.base_test import VMSTest


class test_default_settings_single_export_and_opening_layout(VMSTest):
    """Check single export with default settings.

    Record an archive, select part of archive, invoke export window, check default values,
    export video, check video is exported with those values

    Open a saved layout via the resource tree in all possible ways.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/20860
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1307

    Selection-Tag: 20860
    Selection-Tag: 1307
    Selection-Tag: layouts
    Selection-Tag: export
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        dt = datetime.fromisoformat('2020-11-05T11:11:28').replace(
            tzinfo=server_vm.os_access.get_datetime().tzinfo,
            )
        exit_stack.enter_context(playing_testcamera(machine_pool, server_vm.os_access, 'samples/overlay_test_video.mp4'))
        [test_camera_1] = server_vm.api.add_test_cameras(0, 1)
        server_vm.default_archive().camera_archive(test_camera_1.physical_id).save_media_sample(
            dt,
            SampleMediaFile(gui_prerequisite_store.fetch('samples/overlay_test_video.mp4')),
            )
        server_vm.api.rebuild_main_archive()
        testkit_api, _ = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, test_camera_1.name)
        hid = HID(testkit_api)
        export_settings = Timeline(testkit_api, hid).open_export_video_dialog_for_interval(0, 0.9)
        assert not export_settings.timestamp_feature.enabled()
        assert not export_settings.image_feature.enabled()
        assert not export_settings.text_feature.enabled()
        assert not export_settings.rapid_review_feature.enabled()
        assert not export_settings.single_camera_settings.get_apply_filters_checkbox_state()
        dir_name, file_name = export_settings.exporter().current_path()
        current_export_path = str(client_installation.os_access.path(dir_name, file_name))
        client_tz = client_installation.os_access.get_datetime().tzinfo
        exported_file_client_dt = client_installation.archive_dir / f"{test_camera_1.name}_{dt.astimezone(client_tz):%Y_%m_%d_%-I%p_%M_%S}.mkv"
        exported_file_server_dt = client_installation.archive_dir / f"{test_camera_1.name}_{dt:%Y_%m_%d_%I%p_%M_%S}.mkv"
        # TODO: Make check stricter https://networkoptix.atlassian.net/browse/FT-2568
        if current_export_path == str(exported_file_server_dt):
            exported_file = exported_file_server_dt
        elif current_export_path == str(exported_file_client_dt):
            exported_file = exported_file_client_dt
        else:
            raise RuntimeError(
                f'Unexpected default export file name.'
                f' Expected: {str(exported_file_server_dt)!r} (VMS 6.0).'
                f' {str(exported_file_client_dt)!r} (VMS 6.1 and higher).'
                f' Actual: {current_export_path!r}')
        export_settings.export()
        assert client_installation.os_access.path(exported_file).exists()
        rtree = ResourceTree(testkit_api, hid)
        rtree.get_local_file(exported_file.name).open_in_new_tab()
        TimelineNavigation(testkit_api, hid).pause_and_to_begin()
        loaded = SavedImage(gui_prerequisite_store.fetch('test20860/result.png'))
        Scene(testkit_api, hid).wait_until_first_item_is_similar_to(loaded)

        tab_bar = LayoutTabBar(testkit_api, hid)
        tab_bar.close('TestLayout')
        rtree.get_layout('TestLayout').open()
        assert tab_bar.is_open('TestLayout')
        tab_bar.close('TestLayout')
        rtree.get_layout('TestLayout').open_in_new_tab()
        assert tab_bar.is_open('TestLayout')
        tab_bar.close('TestLayout')
        rtree.get_layout('TestLayout').drag_n_drop_on_scene()
        assert tab_bar.is_open('TestLayout')


if __name__ == '__main__':
    exit(test_default_settings_single_export_and_opening_layout().main())
