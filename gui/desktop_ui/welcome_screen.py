# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import re
import time
from typing import List
from typing import Optional
from typing import Union

from gui import testkit
from gui.desktop_ui.widget import Widget
from gui.desktop_ui.wrappers import Button
from gui.desktop_ui.wrappers import Checkbox
from gui.desktop_ui.wrappers import EditableQMLComboBox
from gui.desktop_ui.wrappers import QLineEdit
from gui.desktop_ui.wrappers import QQuickImage
from gui.desktop_ui.wrappers import QQuickPopupItem
from gui.desktop_ui.wrappers import QmlScrollBar
from gui.testkit.hid import HID
from gui.testkit.testkit import TestKit

_logger = logging.getLogger(__name__)


class WelcomeScreen:

    def __init__(self, api: TestKit, hid: HID):
        self._obj = Widget(api, {
            "type": "nx::vms::client::desktop::WelcomeScreen",
            "unnamed": 1,
            "visible": 1,
            })
        self._api = api
        self._hid = hid

    def _get_search_field(self):
        search_field = self._obj.find_child({
            "echoMode": 0,
            "id": "searchEdit",
            "type": "SearchEdit",
            "unnamed": 1,
            "visible": True,
            })
        return QLineEdit(self._hid, search_field)

    def _get_grid(self):
        return self._obj.find_child({
            "id": "grid",
            "type": "GridView",
            "unnamed": 1,
            "visible": True,
            })

    def get_system_tiles(self) -> List['_SystemTile']:
        _logger.info('%r: Looking for system tiles', self)
        tiles = self._get_grid().find_children({
            "type": "Tile",
            "visible": True,
            })
        tile_objs = []
        for tile in tiles:
            try:
                # Sometimes tile can disappear from welcome screen
                tile_objs.append(_SystemTile(tile, self._api, self._hid))
            except testkit.ObjectNotFound:
                pass
        return tile_objs

    def _get_tile_by_type_name(self, type_name: str):
        tile = self._get_grid().find_child({
            "checkable": False,
            "type": type_name,
            "unnamed": 1,
            "visible": True,
            })
        return tile

    def get_cloud_tile(self):
        _logger.info('WelcomeScreen: Getting Cloud tile')
        tile = self._get_tile_by_type_name("CloudTile")
        return _CloudTile(tile, self._hid)

    def get_connect_tile(self):
        _logger.info('WelcomeScreen: Getting Connect tile')
        tile = self._get_tile_by_type_name("ConnectTile")
        return _ConnectTile(tile, self._hid)

    def _get_system_tile(self, title_text_pattern) -> Optional['_SystemTile']:
        # Fixing unstable attempt to get system tile object.
        time.sleep(2)
        for tile in self.get_system_tiles():
            if re.compile(title_text_pattern).match(tile.get_title()) is not None:
                return tile
        return None

    def tile_exists(self, title):
        _logger.info('%r: Looking for tile with title: %s', self, title)
        try:
            tile = self._get_system_tile(title)
            return True if tile is not None else False
        except testkit.ObjectAttributeNotFound as e:
            if "Attempt to access a property of a null object" in str(e):
                return False
            raise e
        except RuntimeError as e:
            if "Property read failed" in str(e):
                return False
            raise e

    def wait_for_tile_appear(self, title, wait_time: float):
        _logger.info(
            '%r: Wait for tile with title %s appears. Timeout: %s second(s)',
            self, title, wait_time)
        start_time = time.monotonic()
        while True:
            if self.tile_exists(title):
                return
            if time.monotonic() - start_time > wait_time:
                raise RuntimeError(f"Tile {title!r} is not shown on welcome screen")
            time.sleep(1)

    def wait_for_tile_disappear(self, wait_time: float, title: str):
        _logger.info(
            '%r: Wait for tile with title %s disappears. Timeout: %s second(s)',
            self, title, wait_time)
        start_time = time.monotonic()
        while True:
            if not self.tile_exists(title):
                return
            if time.monotonic() - start_time > wait_time:
                raise RuntimeError("Tile is shown on welcome screen")
            time.sleep(1)

    def get_tile_by_system_name(self, title):
        _logger.info('%r: Looking for system tile with title: %s', self, title)
        system_tile = self._get_system_tile(title)
        if system_tile is None:
            raise RuntimeError(f"System tile with title: {title!r} not found on welcome screen")
        return system_tile

    def get_tile_by_subtitle(self, subtitle):
        # Fixing unstable attempt to get system tile object.
        time.sleep(2)
        for tile in self.get_system_tiles():
            if tile.get_subtitle() == subtitle:
                return tile
        return None

    def _get_all_tiles(self) -> List['_Tile']:
        tiles = [*self.get_system_tiles()]
        if self.get_cloud_tile().is_accessible():
            tiles.append(self.get_cloud_tile())
        if self.get_connect_tile().is_accessible():
            tiles.append(self.get_connect_tile())
        return tiles

    def get_tile_count(self):
        return len(self._get_all_tiles())

    def get_row_count(self):
        rows = {int(tile.bounds().y) for tile in self._get_all_tiles()}
        _logger.debug(rows)
        return len(rows)

    def _get_logo(self):
        logo = self._obj.find_child({
            "id": "logo",
            "source": re.compile("skin/welcome_page/logo.png"),
            "type": "Image",
            "unnamed": 1,
            "visible": True,
            })
        return QQuickImage(logo)

    def get_logo_size(self):
        return self._get_logo().get_painted_size()

    def click_logo(self):
        _logger.info('%r: Click logo', self)
        self._hid.mouse_left_click_on_object(self._get_logo())

    def get_open_tile(self) -> '_OpenTileItem':
        tile = _OpenTileItem(self._api, self._hid)
        if not tile.is_accessible():
            raise RuntimeError("No 'Connect to the system' dialog appears")
        return tile

    def has_open_tile(self):
        tile = _OpenTileItem(self._api, self._hid)
        return tile.is_accessible()

    def has_links(self, *links):
        footer = self._obj.find_child({
            "id": "footer",
            "type": "Item",
            "unnamed": 1,
            "visible": True,
            })
        for link in links:
            link_widget = footer.find_child({
                "checkable": False,
                "type": "LinkButton",
                "unnamed": 1,
                "visible": True,
                'text': link,
                })
            if not link_widget.is_accessible():
                return False
        return True

    def has_client_version(self):
        footer = self._obj.find_child({
            "id": "footer",
            "type": "Item",
            "unnamed": 1,
            "visible": True,
            })
        version = footer.find_child({
            "type": "Label",
            "unnamed": 1,
            "visible": True,
            })
        return version.is_accessible()

    def _get_display_mode_menu_button(self):
        button = self._obj.find_child({
            "checkable": False,
            "id": "visibilityButton",
            "type": "VisibilityButton",
            "unnamed": 1,
            "visible": True,
            })
        return Button(button)

    def get_display_mode(self) -> str:
        return self._get_display_mode_menu_button().get_text()

    def _get_display_mode_menu(self):
        overlay = self._obj.find_child({
            "type": "Overlay",
            "unnamed": 1,
            "visible": True,
            })
        display_mode_menu = overlay.find_child({
            "type": "PopupItem",
            "unnamed": 1,
            "visible": True,
            })
        return QQuickPopupItem(display_mode_menu, self._hid)

    def set_display_mode(self, menu_option: Union[str, re.Pattern]):
        _logger.info('%r: Set menu option: %s', self, menu_option)
        self._hid.mouse_left_click_on_object(self._get_display_mode_menu_button())
        self._get_display_mode_menu().wait_for_accessible(1)
        self._get_display_mode_menu().activate_item(menu_option)
        time.sleep(2)

    def get_display_mode_options(self):
        self._hid.mouse_left_click_on_object(self._get_display_mode_menu_button())
        options = self._get_display_mode_menu().get_options()
        self._hid.mouse_left_click_on_object(self._get_display_mode_menu_button())
        return options

    def wait_for_accessible(self, timeout: float = 3):
        self._obj.wait_for_accessible(timeout)

    def _get_scrollbar(self):
        scrollbar = self._obj.find_child({
            "id": "scrollBar",
            "orientation": 2,
            "type": "ScrollBar",
            "unnamed": 1,
            "visible": True,
            })
        return QmlScrollBar(scrollbar)

    def has_scrollbar(self):
        self._get_scrollbar().is_accessible()

    def scroll_to_tile(self, tile):
        _logger.info('%r: Scroll to tile: %s', self, tile)
        self._get_scrollbar().scroll_to_object(tile)

    def search(self, text):
        _logger.info('%r: Looking for tiles by text: %s', self, text)
        self._get_search_field().type_text(text)

    def get_search_text(self):
        return self._get_search_field().get_text()

    def clear_search(self):
        _logger.info('%r: Clear search field', self)
        self._get_search_field().clear_field()

    def search_is_active(self):
        return self._get_search_field().is_active()

    def get_search_field_width(self):
        return self._get_search_field().get_width()


class _OpenTileItem:

    def __init__(self, api: TestKit, hid: HID):
        self._api = api
        self._hid = hid
        self._obj = Widget(api, {
            "type": "OpenedTileItem",
            "unnamed": 1,
            "visible": True,
            })

    def get_connect_button(self):
        connect_button = self._obj.find_child({
            "checkable": False,
            "id": "connectButton",
            "text": "Connect",
            "type": "Button",
            "unnamed": 1,
            "visible": True,
            })
        return Button(connect_button)

    def get_address_combobox(self):
        address_combobox = self._obj.find_child({
            "id": "hostChooseItem",
            "type": "ComboBox",
            "unnamed": 1,
            "visible": True,
            })
        return EditableQMLComboBox(address_combobox)

    def get_user_combobox(self):
        user_combobox = self._obj.find_child({
            "id": "loginChooseItem",
            "type": "ComboBox",
            "unnamed": 1,
            "visible": True,
            })
        return EditableQMLComboBox(user_combobox)

    def get_password_qline(self):
        password_qline = self._obj.find_child({
            "echoMode": 2,
            "id": "passwordItem",
            "type": "TextField",
            "unnamed": 1,
            "visible": True,
            })
        return QLineEdit(self._hid, password_qline)

    def get_remember_password_checkbox(self):
        password_checkbox = self._obj.find_child({
            "checkable": True,
            "id": "savePasswordCheckbox",
            "text": "Remember me",
            "type": "CheckBox",
            "unnamed": 1,
            "visible": True,
            })
        return Checkbox(self._hid, password_checkbox)

    def close(self):
        _logger.info('%r: Close', self)
        close_button = self._obj.find_child({
            "checkable": False,
            "id": "closeButton",
            "type": "Button",
            "unnamed": 1,
            "visible": True,
            })
        self._hid.mouse_left_click_on_object(close_button)

    def set(self, address, user, password, remember_password=False):
        _logger.info(
            '%r: Fill: address %s, user %s, password %s, remember_password=%s',
            self, address, user, password, remember_password)
        self.get_address_combobox().set_text(address)
        self.get_user_combobox().set_text(user)
        self.get_password_qline().type_text(password)
        self.get_remember_password_checkbox().set(remember_password)

    def get_connection_error_message(self):
        error_msg_obj = Widget(self._api, {
            'container': self._obj.wait_for_object(),
            'id': 'connectErrorItem',
            'visible': True,
            })
        error_msg_obj.wait_for_accessible(20)
        return error_msg_obj.get_text()

    def get_login_error_message(self):
        error_msg_obj = Widget(self._api, {
            'container': self._obj.wait_for_object(),
            'id': 'loginErrorItem',
            'visible': True,
            })
        error_msg_obj.wait_for_accessible(5)
        return error_msg_obj.get_text()

    def is_accessible(self):
        return self._obj.is_accessible_timeout(10)


class _Tile:

    def __init__(self, obj: Widget, hid: HID):
        self._obj = obj
        self._hid = hid

    def __repr__(self):
        return f'<{self.__class__.__name__}: {self._obj!r}>'

    def _has_image(self, file_source_pattern: re.Pattern) -> bool:
        image = self._obj.find_child({
            "source": file_source_pattern,
            "type": "Image",
            "unnamed": 1,
            "visible": True,
            })
        return image.is_accessible_timeout(0.5)

    def click(self):
        _logger.info('%r: Click', self)
        self._hid.mouse_left_click_on_object(self._obj)

    def is_accessible(self):
        return self._obj.is_accessible_timeout(3)

    def bounds(self):
        return self._obj.bounds()


class _SystemTile(_Tile):

    def __init__(self, obj: Widget, api: TestKit, hid: HID):
        super().__init__(obj, hid)
        self._api = api

    def get_subtitle(self) -> str:
        label = self._obj.find_child({
            'type': 'Label',
            'visible': True,
            'id': 'address',
            })
        return label.get_text()

    def get_title(self) -> str:
        return str(self._obj.wait_property('title'))

    def has_dropdown_menu(self) -> bool:
        return self._get_dropdown_menu_button().is_visible()

    def _get_dropdown_menu_button(self):
        button = self._obj.find_child({
            'type': 'MenuButton',
            })
        return button

    def _trash_button(self):
        button = self._obj.find_child({
                'type': 'Button',
                'id': 'deleteButton',
                })
        return button

    def has_trash_button(self) -> bool:
        return self._trash_button().is_visible()

    def has_gear_icon(self) -> bool:
        return self._has_image(re.compile(r'settings.*\.svg'))

    def has_cloud_icon(self) -> bool:
        return self._has_image(re.compile(r'cloud\.svg'))

    def is_pending(self) -> bool:
        children = self._obj.find_children({
            "id": "anchorTag",
            "type": "Tag",
            "unnamed": 1,
            "visible": True,
            })
        for child in children:
            if child.get_text() == 'Pending':
                return True
        return False

    def is_favorite(self) -> bool:
        # Icon star_full.svg is used in VMS 6.0, star.svg - in higher versions.
        return self._has_image(re.compile(r'(star_full|star)\.svg'))

    def is_hidden(self) -> bool:
        # Icon eye_full.png is used in VMS 6.0, eye_closed.svg - in higher versions.
        return self._has_image(re.compile(r'(eye_full|eye_closed)\.svg'))

    def is_online(self) -> bool:
        children = self._obj.find_children({
            "type": "Tag",
            "unnamed": 1,
            "visible": True,
            })
        for child in children:
            text = child.get_text()
            if text == 'Offline':
                return False
            else:
                _logger.info(f"Tile under test has text {text}")
        return True

    def _is_unreachable(self) -> bool:
        children = self._obj.find_children({
            "type": "Tag",
            "unnamed": 1,
            "visible": True,
            })
        for child in children:
            text = child.get_text()
            if text == 'Unreachable':
                return True
            else:
                _logger.info(f"Tile under test has text {text}")
        return False

    def _get_dropdown_menu(self):
        overlay = Widget(self._api, {
            "type": "Overlay",
            "unnamed": 1,
            "visible": True,
            })
        dropdown_menu = overlay.find_child({
            "type": "PopupItem",
            "unnamed": 1,
            "visible": True,
            })
        return QQuickPopupItem(dropdown_menu, self._hid)

    def choose_dropdown_menu_option(self, name):
        _logger.info('%r: Open dropdown menu', self)
        button = self._get_dropdown_menu_button()
        button.wait_for_accessible()
        self._hid.mouse_left_click_on_object(button)
        self._get_dropdown_menu().wait_for_accessible()
        _logger.info('%r: Choose dropdown menu option: %s', self, name)
        self._get_dropdown_menu().activate_item(name)

    def has_dropdown_menu_option(self, option: str) -> bool:
        button = self._get_dropdown_menu_button()
        button.wait_for_accessible()
        self._hid.mouse_left_click_on_object(button)
        return option in self._get_dropdown_menu().get_options()

    def list_dropdown_menu_options(self) -> List[str]:
        button = self._get_dropdown_menu_button()
        button.wait_for_accessible()
        self._hid.mouse_left_click_on_object(button)
        return self._get_dropdown_menu().get_options()

    def remove_using_dropdown_menu(self):
        self.choose_dropdown_menu_option('Delete')

    def remove_using_shift(self):
        _logger.info('%r: Remove using Shift', self)
        self._hid.keyboard_press('Shift')
        self._trash_button().wait_for_accessible()
        self._hid.mouse_left_click_on_object(self._trash_button())
        self._hid.keyboard_release('Shift')

    def forget_password(self):
        _logger.info('%r: Forget password', self)
        self.choose_dropdown_menu_option('Edit')
        _OpenTileItem(self._api, self._hid).get_remember_password_checkbox().set(False)
        _OpenTileItem(self._api, self._hid).close()
        time.sleep(2)

    def open(self):
        self.wait_until_online()
        self.click()

    def wait_until_online(self, timeout: float = 5):
        started_at = time.monotonic()
        while True:
            if self.is_online():
                return
            elif time.monotonic() - started_at > timeout:
                raise RuntimeError(f'System tile {self!r} looks as offline')
            _logger.info("%r is still offline", self)

    def wait_until_offline(self):
        started_at = time.monotonic()
        while True:
            if not self.is_online():
                return
            elif time.monotonic() - started_at > 5:
                raise RuntimeError(f'System tile {self!r} looks as online')
            _logger.info("%r is still online", self)
            time.sleep(0.5)

    def wait_until_unreachable(self, timeout: float = 5):
        started_at = time.monotonic()
        while True:
            if self._is_unreachable():
                return
            elif time.monotonic() - started_at > timeout:
                raise RuntimeError(f'System tile {self!r} looks as reachable')
            _logger.info("%r is still reachable", self)
            time.sleep(0.5)


class _CloudTile(_Tile):

    def has_correct_icon(self):
        return self._has_image(re.compile(r'connect_to_cloud.*\.svg'))


class _ConnectTile(_Tile):

    def has_correct_icon(self):
        return self._has_image(re.compile(r'connect_to_server.*\.svg'))
