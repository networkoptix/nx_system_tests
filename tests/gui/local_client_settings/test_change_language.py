# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client
from gui.desktop_ui.dialogs.local_settings import LocalSettingsDialog
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.messages import MessageBox
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_change_language(VMSTest):
    """Change language.

    # https://networkoptix.testrail.net/index.php?/cases/view/6732

    Selection-Tag: 6732
    Selection-Tag: local_settings
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        client_installation = exit_stack.enter_context(machine_pool.create_and_setup_only_client())
        testkit_api_1 = start_desktop_client(machine_pool.get_testkit_port(), client_installation)
        hid_1 = HID(testkit_api_1)
        main_menu_1 = MainMenu(testkit_api_1, hid_1)
        local_settings_dialog = main_menu_1.open_local_settings_dialog()
        local_settings_dialog.activate_tab('Look and Feel')
        local_settings_dialog.look_and_feel_tab.set_locale('Deutsch')
        local_settings_dialog.click_ok_button()
        message_box = MessageBox(testkit_api_1, hid_1).wait_until_appears(20)
        assert message_box.get_title() == 'Some changes will take effect only after Nx Witness Client restart'
        message_box.close_by_button('Restart Later')
        local_settings_dialog = main_menu_1.open_local_settings_dialog()
        local_settings_dialog.activate_tab('Look and Feel')
        assert local_settings_dialog.look_and_feel_tab.get_locale() == 'Deutsch'
        client_installation.kill_client_process()

        testkit_api_2 = start_desktop_client(machine_pool.get_testkit_port(), client_installation)
        hid_2 = HID(testkit_api_2)
        MainMenu(testkit_api_2, hid_2).activate_items_de('Lokale Einstellungen...')
        local_settings_dialog = LocalSettingsDialog(testkit_api_2, hid_2)
        local_settings_dialog.activate_tab('Look and Feel')
        local_settings_dialog.look_and_feel_tab.set_locale('English (US)')
        local_settings_dialog.click_german_ok_button()
        MessageBox(testkit_api_2, hid_2).click_button_with_text('Jetzt neustarten')

        client_installation.kill_client_process()
        testkit_api_3 = start_desktop_client(machine_pool.get_testkit_port(), client_installation)
        hid_3 = HID(testkit_api_3)
        local_settings_dialog = MainMenu(testkit_api_3, hid_3).open_local_settings_dialog()
        local_settings_dialog.activate_tab('Look and Feel')
        assert local_settings_dialog.look_and_feel_tab.get_locale() == 'English (US)'


if __name__ == '__main__':
    exit(test_change_language().main())
