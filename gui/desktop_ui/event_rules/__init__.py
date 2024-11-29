# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from gui.desktop_ui.event_rules._abstract_event_rules_dialog import AbstractEventRulesDialog
from gui.desktop_ui.event_rules._legacy_event_rules_dialog import LegacyEventRulesDialog
from gui.desktop_ui.event_rules._qml_event_rules_dialog import QmlEventRulesDialog
from gui.testkit import TestKit
from gui.testkit.hid import HID

__all__ = [
    'AbstractEventRulesDialog',
    'get_event_rules_dialog',
    ]


def get_event_rules_dialog(api: TestKit, hid: HID) -> AbstractEventRulesDialog:
    legacy_dialog = LegacyEventRulesDialog(api, hid)
    qml_dialog = QmlEventRulesDialog(api, hid)
    if legacy_dialog.is_accessible():
        return legacy_dialog
    elif qml_dialog.is_accessible():
        return qml_dialog
    else:
        raise RuntimeError('Unknown Event Rules Dialog')
