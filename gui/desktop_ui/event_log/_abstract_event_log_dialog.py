# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from abc import ABCMeta
from abc import abstractmethod

from gui.desktop_ui.wrappers import Button
from gui.desktop_ui.wrappers import ComboBox
from gui.desktop_ui.wrappers import QTable


class AbstractEventLogDialog(metaclass=ABCMeta):

    @abstractmethod
    def get_action_filter(self) -> ComboBox:
        pass

    @abstractmethod
    def get_device_filter(self) -> Button:
        pass

    @abstractmethod
    def get_event_filter(self) -> ComboBox:
        pass

    @abstractmethod
    def _get_table(self) -> QTable:
        pass

    @abstractmethod
    def is_ready(self) -> bool:
        pass

    @abstractmethod
    def has_event_with_action(self, event: str, action: str) -> bool:
        pass

    @abstractmethod
    def has_event_with_source_and_action(self, event: str, source: str, action: str) -> bool:
        pass

    @abstractmethod
    def get_description_of_event_with_action(self, event: str, action: str) -> str:
        pass

    @abstractmethod
    def activate_source_context_menu(self, source: str, context_menu_option: str):
        pass

    @abstractmethod
    def wait_until_appears(self):
        pass

    @abstractmethod
    def is_accessible(self) -> bool:
        pass
