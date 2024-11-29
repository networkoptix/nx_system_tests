# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from gui.desktop_ui.event_log._abstract_event_log_dialog import AbstractEventLogDialog
from gui.desktop_ui.event_log._actual_event_log_dialog import ActualEventLog
from gui.desktop_ui.event_log._legacy_event_log_dialog import LegacyEventLog
from gui.testkit import TestKit
from gui.testkit.hid import HID

__all__ = [
    'AbstractEventLogDialog',
    'get_event_log_dialog',
    ]


def get_event_log_dialog(api: TestKit, hid: HID) -> AbstractEventLogDialog:
    legacy_dialog = LegacyEventLog(api, hid)
    actual_dialog = ActualEventLog(api, hid)
    if legacy_dialog.is_accessible():
        return legacy_dialog
    elif actual_dialog.is_accessible():
        return actual_dialog
    else:
        raise RuntimeError('Unknown Event Log Dialog')
