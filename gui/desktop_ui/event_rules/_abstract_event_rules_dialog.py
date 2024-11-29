# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from abc import ABCMeta
from abc import abstractmethod
from typing import NamedTuple
from typing import Optional


class AbstractEventRulesDialog(metaclass=ABCMeta):

    @abstractmethod
    def click_add_rule_button(self):
        pass

    @abstractmethod
    def click_delete_button(self):
        pass

    @abstractmethod
    def close(self):
        pass

    @abstractmethod
    def click_apply_button(self):
        pass

    @abstractmethod
    def get_search_field(self):
        pass

    @abstractmethod
    def row_cell_images(self, event, action, target):
        pass

    @abstractmethod
    def get_row_by_values(
            self, event: str, action: str, target: Optional[str] = None):
        pass

    @abstractmethod
    def select_rule(self, event: str, action: str):
        pass

    @abstractmethod
    def get_add_rule_dialog(self):
        pass

    @abstractmethod
    def wait_for_accessible(self, timeout_sec: float):
        pass

    @abstractmethod
    def is_accessible(self):
        pass

    @staticmethod
    @abstractmethod
    def event_names() -> 'EventNames':
        pass

    @staticmethod
    @abstractmethod
    def action_names() -> 'ActionNames':
        pass

    @abstractmethod
    def wait_until_appears(self):
        pass


class ActionNames(NamedTuple):
    BOOKMARK: str
    TEXT_OVERLAY: str
    HTTP_REQUEST: str
    SHOW_DESKTOP_NOTIFICATION: str
    CAMERA_RECORDING: str
    MOBILE_NOTIFICATION: str
    SEND_EMAIL: str
    SET_FULLSCREEN: str


class EventNames(NamedTuple):
    MOTION: str
    GENERIC: str
    CAMERA_DISCONNECTION: str
    SOFT_TRIGGER: str
    TRIGGER_MOTION: str
    TRIGGER_GENERIC: str
    TRIGGER_CAMERA_DISCONNECTION: str
    TRIGGER_SOFT_TRIGGER: str
    ANALYTICS_EVENT: str
