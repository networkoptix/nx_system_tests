# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from _internal.service_registry import gui_prerequisite_store
from directories import get_run_dir
from doubles.video.ffprobe import SampleMediaFile
from gui.gui_test_stand import GuiTestStand
from gui.mobile_ui.app_window import ApplicationWindow
from gui.mobile_ui.connect_to_server import ConnectToServer
from gui.mobile_ui.scene import Scene
from gui.mobile_ui.warning_dialog import WarningDialog
from gui.mobile_ui.welcome_screen import WelcomeScreen
from installation import ClassicInstallerSupplier
from mediaserver_api import EventCondition
from mediaserver_api import EventState
from mediaserver_api import EventType
from mediaserver_api import Groups
from mediaserver_api import LdapSearchBase
from mediaserver_api import RuleAction
from mediaserver_api import RuleActionType
from mediaserver_scenarios.testcamera_setup import similar_playing_testcameras
from os_access.ldap.server_installation import GeneratedLDAPUser
from tests.base_test import VMSTest


class test_ldap_advanced_viewer(VMSTest):
    """LDAP User. Advanced Viewer.

    Selection-Tag: 116690
    Selection-Tag: mobile-gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/116690
    """

    def _run(self, args, exit_stack):
        installer_supplier = ClassicInstallerSupplier(args.distrib_url)
        installer_supplier.distrib().assert_not_older_than('vms_6.1', "Mobile tests only supported by VMS 6.1 and newer")
        machine_pool = GuiTestStand(installer_supplier, get_run_dir())
        mediaserver_unit, ldap_server_unit = exit_stack.enter_context(machine_pool.setup_server_ldap())
        server_vm = mediaserver_unit.installation()
        ldap_server = ldap_server_unit.installation()
        ldap_address = ldap_server_unit.subnet_ip()
        generated_ldap_user = GeneratedLDAPUser('Test', 'User')
        ldap_server.add_users([generated_ldap_user.attrs()])
        search_base_users = LdapSearchBase(
            base_dn=ldap_server.users_ou(),
            filter='',
            name='users',
            )
        server_vm.api.set_ldap_settings(
            host=str(ldap_address),
            admin_dn=ldap_server.admin_dn(),
            admin_password=ldap_server.password(),
            search_base=[search_base_users],
            )
        server_vm.api.sync_ldap_users()
        exit_stack.enter_context(similar_playing_testcameras(
            machine_pool=machine_pool,
            os_access=server_vm.os_access,
            primary_prerequisite='samples/overlay_test_video.mp4',
            count=2,
            ))
        [ldap_user] = [user for user in server_vm.api.list_users() if user.is_ldap]
        server_vm.api.add_user_to_group(ldap_user.id, Groups.ADVANCED_VIEWERS)
        [test_camera_1, test_camera_2] = server_vm.api.add_test_cameras(0, 2)
        test_camera_1_archive = server_vm.default_archive().camera_archive(test_camera_1.physical_id)
        media_file = SampleMediaFile(gui_prerequisite_store.fetch('samples/dynamic_test_video.mp4'))
        now = datetime.now(timezone.utc)
        offset_seconds = 3600
        test_camera_1_archive.save_media_sample(now - timedelta(seconds=offset_seconds), media_file)
        server_vm.api.rebuild_main_archive()

        bookmark_name = 'Test Bookmark'
        server_vm.api.add_bookmark(
            camera_id=test_camera_1.id,
            name=bookmark_name,
            duration_ms=100 * 1000,
            # Bookmark loading may enter an infinite loop if the
            # bookmark start time falls outside the archive chunk.
            # Adding a small time shift can prevent this.
            # See: https://networkoptix.atlassian.net/browse/MOBILE-2041
            start_time_ms=int((now.timestamp() - offset_seconds + 10) * 1000),
            )

        layout_1_name = 'layout_1'
        server_vm.api.add_shared_layout_with_resource(layout_1_name, test_camera_1.id)
        layout_2_name = 'layout_2'
        server_vm.api.add_layout_with_resource(layout_2_name, test_camera_2.id)

        event_rule_action = RuleAction(
                type=RuleActionType.SHOW_TEXT_OVERLAY,
                resource_ids=[str(test_camera_2.id)],
                params={'text': 'FT test trigger'},
                )
        event_name = 'FT Event Name'
        event_condition = EventCondition(
            params={
                'caption': event_name,
                'description': '_bell_on',
                'metadata': {'allUsers': True},
                },
            )
        server_vm.api.add_event_rule(
            event_type=EventType.SOFTWARE_TRIGGER,
            event_state=EventState.UNDEFINED,
            event_resource_ids=[str(test_camera_2.id)],
            action=event_rule_action,
            event_condition=event_condition,
            )

        mobile_client_installation = exit_stack.enter_context(machine_pool.prepared_mobile_client())
        [testkit_api, hid] = mobile_client_installation.start()
        server_ip, server_port = machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm)
        WelcomeScreen(testkit_api, hid).click_connect_button()
        ConnectToServer(testkit_api, hid).connect(
            ip=server_ip,
            port=server_port,
            username=generated_ldap_user.uid,
            password=generated_ldap_user.password,
            )
        WarningDialog(testkit_api, hid).click_button('Connect')
        scene = Scene(testkit_api, hid)
        scene.wait_for_accessible()
        scene_items_count = len(scene.get_camera_items())
        assert scene_items_count == 2, f'Actual scene items count: {scene_items_count}, Expected: 2'
        app_window = ApplicationWindow(testkit_api, hid)
        layouts = app_window.open_left_panel_widget().get_layout_nodes()
        layout_names = [layout.name() for layout in layouts]
        expected_count = 1
        assert len(layout_names) == expected_count, f'Expected layout count: {expected_count}. Actual layouts: {layout_names}'
        root_layout_name = 'All Cameras'
        assert root_layout_name in layout_names, f"{root_layout_name!r} layout should exist. Actual layout names: {layout_names}"
        app_window.close_left_panel()

        video_screen_1 = scene.open_camera_item(test_camera_1.name)
        timeline = video_screen_1.get_timeline()
        assert timeline.is_accessible()
        video_screen_1.get_video_navigator().jump_backward()
        assert video_screen_1.get_video_output_widget().video().has_different_frames()

        bookmarks_dialog = video_screen_1.open_bookmarks_dialog()
        bookmark_player = bookmarks_dialog.open_bookmark(bookmark_name)
        assert bookmark_player.get_video_output_widget().video().has_different_frames()
        app_window.navigate_back()
        bookmark_player.get_playback_panel().wait_for_inaccessible()
        app_window.navigate_back()
        bookmarks_dialog.wait_for_inaccessible()
        video_screen_1.get_video_navigator().wait_for_accessible()  # Ensure video screen loading completed.
        app_window.navigate_back()
        video_screen_1.wait_for_inaccessible()

        video_screen_2 = scene.open_camera_item(test_camera_2.name)
        video_screen_2.activate_soft_trigger()
        actual_trigger_text = video_screen_2.get_soft_trigger_text_label().get_text()
        assert actual_trigger_text == event_name, f'Actual: {actual_trigger_text}. Expected: {event_name}'


if __name__ == '__main__':
    exit(test_ldap_advanced_viewer().main())
