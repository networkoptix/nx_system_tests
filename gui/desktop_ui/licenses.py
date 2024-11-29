# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from typing import List
from typing import NamedTuple
from typing import Sequence

from gui import testkit
from gui.desktop_ui.messages import MessageBox
from gui.desktop_ui.widget import Widget
from gui.desktop_ui.wrappers import BaseWindow
from gui.desktop_ui.wrappers import Button
from gui.desktop_ui.wrappers import QLabel
from gui.desktop_ui.wrappers import QLine
from gui.desktop_ui.wrappers import QLineEdit
from gui.desktop_ui.wrappers import QMLComboBox
from gui.desktop_ui.wrappers import QTable
from gui.desktop_ui.wrappers import TabWidget
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class _DeactivationWindow:

    def __init__(self, api: TestKit, hid: HID):
        self._dialog = BaseWindow(api=api, locator_or_obj={
            "name": "MessageBox",
            "type": "nx::vms::client::desktop::ui::dialogs::LicenseDeactivationReason",
            "visible": 1,
            })
        self._api = api
        self._hid = hid

    def get_confirmation_button(self):
        button = Widget(self._api, {
            "text": "Deactivate",
            "type": "QPushButton",
            "unnamed": 1,
            "visible": 1,
            })
        return Button(button)

    def fill_form(self):
        _logger.info('%r: Deactivate license', self)
        name_line = QLineEdit(self._hid, self._dialog.find_child({
            "type": "QLineEdit",
            "unnamed": 1,
            "visible": 1,
            "occurrence": 1,
            }))
        email_line = QLineEdit(self._hid, self._dialog.find_child({
            "occurrence": 2,
            "type": "QLineEdit",
            "unnamed": 1,
            "visible": 1,
            }))
        reason_combo = QMLComboBox(self._dialog.find_child({
            "type": "QComboBox",
            "unnamed": 1,
            "visible": 1,
            }))
        name_line.type_text('Squish Test User')
        email_line.type_text('squish@networkoptix.com')
        reason_combo.select('Other Reason')

        reason_qline = QLineEdit(self._hid, self._dialog.find_child({
            "type": "QTextEdit",
            "unnamed": 1,
            "visible": 1,
            }))
        reason_qline.set_text_without_validation('Test Reason')
        email_line.click()

        next_button = Button(self._dialog.find_child({
            "text": "Next",
            "type": "QPushButton",
            "unnamed": 1,
            "visible": 1,
            }))
        self._hid.mouse_left_click_on_object(next_button)
        self.get_confirmation_button().wait_for_accessible()


class _LicenseData(NamedTuple):
    license_type: str
    channels: str
    license_key: str
    expires: str
    server: str
    status: str


class LicensesTab:

    def __init__(self, api: TestKit, hid: HID):
        self._api = api
        self._hid = hid
        self._overlay = Widget(api, {
            "name": "LicenseManagerWidget",
            "visible": 1,
            })
        self.license_table = QTable(
            self._hid,
            Widget(api, {
                "name": "gridLicenses",
                "type": "nx::vms::client::desktop::TreeView",
                "visible": 1,
                }),
            ['license_type', 'channels', 'license_key', 'expires', 'server', 'status'],
            )
        self._deactivation_form = _DeactivationWindow(api, hid)

    def get_deactivation_remaining_label(self):
        label = self._overlay.find_child({
            "name": "Deactivations Remaining Value",
            "type": "QLabel",
            "visible": 1,
            })
        return QLabel(label)

    def get_deactivation_error(self):
        label = self._overlay.find_child({
            "type": "QLabel",
            "name": "infoLabel0",
            "visible": 1,
            })
        return QLabel(label)

    def get_quantity_remaining_deactivations_details(self):
        label = self._overlay.find_child({
            "name": "Deactivations Remaining Value",
            "type": "QLabel",
            "visible": 1,
            })
        return QLabel(label)

    def get_deactivate_button(self):
        button = self._overlay.find_child({
            "name": "removeButton",
            "type": "QPushButton",
            "visible": 1,
            "text": "Deactivate",
            })
        return Button(button)

    def get_activate_free_license_button(self):
        button = self._overlay.find_child({
            "name": "activateFreeLicenseButton",
            "type": "nx::vms::client::desktop::BusyIndicatorButton",
            "visible": 1,
            })
        return Button(button)

    def get_remove_button(self):
        button = self._overlay.find_child({
            "name": "removeButton",
            "type": "QPushButton",
            "visible": 1,
            "text": "Remove",
            })
        return Button(button)

    def get_deactivation_error_copy_button(self):
        button = self._overlay.find_child({
            "text": "Copy to Clipboard",
            "type": "nx::vms::client::desktop::ClipboardButton",
            "unnamed": 1,
            "visible": 1,
            })
        return Button(button)

    def get_license_details_code_label(self):
        label = self._overlay.find_child({
            "name": "License Key Value",
            "type": "QLabel",
            "visible": 1,
            })
        return QLabel(label)

    def get_manual_activation_message(self):
        label = self._overlay.find_child({
            "name": "manualActivationTextWidget",
            "type": "QLabel",
            "visible": 1,
            })
        return QLabel(label)

    def is_open(self):
        return self._overlay.is_accessible()

    def get_row_count(self):
        return len(self.license_table.all_rows())

    def deactivate_button_is_accessible(self) -> bool:
        return self.get_deactivate_button().is_accessible()

    def quantity_remaining_deactivations_details_is_accessible(self) -> bool:
        return self.get_quantity_remaining_deactivations_details().is_accessible()

    def activate_free_license(self):
        _logger.info('%r: Activate free license', self)
        self._hid.mouse_left_click_on_object(self.get_activate_free_license_button())
        message_dialog = MessageBox(self._api, self._hid)
        message_dialog.wait_until_has_label('License activated', timeout=10)
        message_dialog.close_by_button('OK')

    def is_free_license_activated(self):
        found = self.license_table.get_row_index_by_values(
            license_key='0000-0000-0000-0005',
            license_type='Time',
            channels='4',
            )
        return found is not None

    def activate_license(self, code):
        _logger.info('%r: Activate license: %s', self, code)
        license_code_line_edit = self._overlay.find_child({
            "name": "onlineKeyEdit",
            "type": "QLineEdit",
            "visible": 1,
            })
        QLineEdit(self._hid, license_code_line_edit).type_text(code)
        activate_button = self._overlay.find_child({
            "name": "activateLicenseButton",
            "type": "nx::vms::client::desktop::BusyIndicatorButton",
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(activate_button)
        if self.is_activation_successful():
            message_dialog = MessageBox(self._api, self._hid)
            message_dialog.close_by_button('OK')
            return True, ''
        else:
            return False, self.get_deactivation_error().get_text()

    def is_activation_successful(self):
        message_dialog = MessageBox(self._api, self._hid)
        message_dialog.wait_until_appears(15)
        return message_dialog.get_title() == 'License activated'

    def select_single_license(self):
        _logger.info('%r: Select first license', self)
        self.license_table.row(0).leftmost_cell().click()
        time.sleep(1)

    def select_all(self):
        _logger.info('%r: Select all licenses', self)
        self.select_single_license()
        self.license_table.select_all_by_hotkey()

    def select_by_status(self, status='OK'):
        _logger.info('%r: Select license by status: %s', self, status)
        row = self.license_table.find_row(status=status)
        row.leftmost_cell().click()
        time.sleep(1)

    def select_by_code(self, code):
        _logger.info('%r: Select license by code: %s', self, code)
        row = self.license_table.find_row(license_key=code)
        row.leftmost_cell().click()

    def deactivate_license(self, code):
        _logger.info('%r: Deactivate license with code: %s', self, code)
        try:
            self.select_by_code(code)
        except (TypeError, testkit.ObjectAttributeNotFound):
            _logger.info("%s: Deactivation of single license", self)
            self.select_single_license()
        finally:
            self.open_deactivation_form()
            self.fill_deactivation_form()
            self.confirm_deactivation()
            self.close_form()

    def deactivate_other_licenses(self, others):
        _logger.info('%r: Deactivate other licenses', self)
        if others != 1 and others != 2:
            raise RuntimeError("Incorrect quantity of licenses for deactivation")
        message_box = MessageBox(self._api, self._hid)
        button = message_box.find_child({
            'type': 'QPushButton',
            'text': f'Deactivate {others} Other'})
        self._hid.mouse_left_click_on_object(button)
        message_box.wait_until_closed()

    def get_license_data(self) -> Sequence[_LicenseData]:
        # Check for table existence was in tests.
        # Is it sometimes or always necessary?
        if not self.license_table.is_accessible():
            return []
        r = []
        for row in self.license_table.all_rows():
            row_data = row.data()
            r.append(_LicenseData(**row_data))
        return r

    def open_details_of_single_license(self):
        _logger.info('%r: Open details of single license', self)
        self.license_table.row(0).leftmost_cell().double_click()

    def _get_ok_button(self):
        button = self._overlay.find_child({
            "type": "QPushButton",
            "visible": 1,
            "unnamed": 1,
            "text": "OK",
            })
        return Button(button)

    def close_details(self):
        _logger.info('%r: Close details', self)
        self._hid.mouse_left_click_on_object(self._get_ok_button())
        self.get_deactivate_button().wait_for_accessible()

    def activate_manually(self, remote_license_file):
        _logger.info('%r: Activate license manually by file: %s', self, remote_license_file)
        browse_file_button = self._overlay.find_child({
            "name": "browseLicenseFileButton",
            "type": "QPushButton",
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(browse_file_button)
        file_name_line_edit = QLineEdit(self._hid, Widget(self._api, {
            "name": "fileNameEdit",
            "type": "QLineEdit",
            "visible": 1,
            }))
        file_name_line_edit.type_text(str(remote_license_file))
        open_file_button = Button(self._overlay.find_child({
            "text": "Open",
            "type": "QPushButton",
            "visible": 1,
            "unnamed": 1,
            }))
        self._hid.mouse_left_click_on_object(open_file_button)
        # If a tooltip with suggested path is appeared.
        if open_file_button.is_accessible():
            self._hid.mouse_left_click_on_object(open_file_button)
        activate_manually_button = self._overlay.find_child({
            "text": "Activate License",
            "type": "nx::vms::client::desktop::BusyIndicatorButton",
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(activate_manually_button)
        time.sleep(1)
        if self.is_activation_successful():
            self._hid.mouse_left_click_on_object(self._get_ok_button())
            return True, ''
        else:
            return False, self.get_deactivation_error().get_text()

    def sort_type_ascending(self):
        _logger.info('%r: Set sort type ascending', self)
        # Clear state after previous sorting.
        self.license_table.click_header('Channels')
        self.license_table.click_header('Type')
        time.sleep(1)

    def change_sort_by_type(self):
        _logger.info('%r: Set sort by type', self)
        self.license_table.click_header('Type')
        time.sleep(1)

    def get_deactivations_in_details(self):
        return self.get_quantity_remaining_deactivations_details().get_text()

    def get_single_code(self) -> str:
        return self.get_all_codes()[0]

    def get_all_codes(self) -> List[str]:
        return self.license_table.column_values('license_key')

    def open_deactivation_form(self):
        _logger.info('%r: Open deactivation form', self)
        self.get_deactivate_button().wait_for_accessible()
        self._hid.mouse_left_click_on_object(self.get_deactivate_button())

    def fill_deactivation_form(self):
        _logger.info('%r: Fill deactivation form', self)
        self._deactivation_form.fill_form()

    def confirm_deactivation(self):
        _logger.info('%r: Confirm deactivation', self)
        confirmation_button = self._deactivation_form.get_confirmation_button()
        self._hid.mouse_left_click_on_object(confirmation_button)
        confirmation_button.wait_for_inaccessible()

    def close_form(self):
        MessageBox(self._api, self._hid).close_by_button('OK')
        time.sleep(1)

    def check_deactivations_in_confirmation(self, quantity: str):
        deactivation_text = self.get_deactivation_error().get_text()
        expected_text = quantity + " deactivation"
        return expected_text in deactivation_text

    def set_activation_tab(self, tab):
        _logger.info('%r: Set Activation tab', self)
        new_license_block = Widget(self._api, {
            "name": "newLicenseGroupBox",
            "type": "QGroupBox",
            "visible": 1,
            })
        activation_tab = new_license_block.find_child({
            "name": "tabWidget",
            "type": "QTabWidget",
            "visible": 1,
            })
        tab = TabWidget(activation_tab).find_tab(tab.title())
        self._hid.mouse_left_click_on_object(tab)
        time.sleep(1)

    def get_hwid(self):
        hwid_line = self._overlay.find_child({
            "name": "hardwareIdEdit",
            "type": "QLineEdit",
            "visible": 1,
            })
        return QLine(hwid_line).get_text()

    def wait_for_licenses_quantity(self, quantity, timeout: float = 3):
        _logger.info(
            '%r: Wait for there are %s licenses. Timeout: %s second(s)',
            self, quantity, timeout)
        start_time = time.monotonic()
        while True:
            if len(self.license_table.all_rows()) == quantity:
                return
            if time.monotonic() - start_time > timeout:
                raise RuntimeError(
                    f"Wrong licenses quantity in table."
                    f"Expected {quantity}, got {len(self.license_table.all_rows())}")
            time.sleep(.5)
