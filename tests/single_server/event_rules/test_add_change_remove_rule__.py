# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from uuid import UUID

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import EventCondition
from mediaserver_api import EventState
from mediaserver_api import EventType
from mediaserver_api import Rule
from mediaserver_api import RuleAction
from mediaserver_api import RuleActionType
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_add_change_remove_rule(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver = one_mediaserver.mediaserver()
    audit_trail = mediaserver.api.audit_trail()
    event_type = EventType.CAMERA_DISCONNECT
    event_state = EventState.UNDEFINED
    action = RuleAction(RuleActionType.SHOW_POPUP)
    rule_id = mediaserver.api.add_event_rule(
        event_type=event_type,
        event_state=event_state,
        action=action,
        )
    event_rule = mediaserver.api.get_event_rule(rule_id)
    assert event_rule.action == action.type
    assert event_rule.event == event_type
    assert event_rule.state == event_state
    assert not event_rule.data["eventCondition"]["omitDbLogging"]

    record = audit_trail.wait_for_one()
    [event_from_audit_record, action_from_audit_record] = Rule.parse_audit_record_params(
        record.params)
    assert record.type == mediaserver.api.audit_trail_events.EVENT_RULE_UPDATE
    assert event_from_audit_record == event_type
    assert action_from_audit_record == action.type
    [camera] = mediaserver.api.add_test_cameras(0, 1)
    example_email = "mail@example.local"
    event_type = EventType.CAMERA_MOTION
    event_state = EventState.UNDEFINED
    action = RuleAction.send_mail(example_email)
    event_condition = EventCondition(omit_db_logging=True)
    mediaserver.api.modify_event_rule(
        rule_id=rule_id,
        event_type=event_type,
        event_state=event_state,
        action=action,
        event_resource_ids=[str(camera.id)],
        event_condition=event_condition,
        )
    event_rule = mediaserver.api.get_event_rule(rule_id)
    assert event_rule.action == action.type
    assert event_rule.event == event_type
    assert event_rule.state == event_state
    assert event_rule.data['actionParams']['emailAddress'] == example_email
    assert event_rule.data["eventCondition"]["omitDbLogging"]
    assert event_rule.data["eventResourceIds"]
    assert UUID(event_rule.data["eventResourceIds"][0]) == camera.id

    [add_camera_record, modify_rule_record] = audit_trail.wait_for_sequence()
    [event_from_audit_record, action_from_audit_record] = Rule.parse_audit_record_params(
        modify_rule_record.params)
    assert add_camera_record.type == mediaserver.api.audit_trail_events.CAMERA_INSERT
    assert modify_rule_record.type == mediaserver.api.audit_trail_events.EVENT_RULE_UPDATE
    assert event_from_audit_record == event_type
    assert action_from_audit_record == action.type

    mediaserver.api.remove_event_rule(rule_id)
    record = audit_trail.wait_for_one()
    [event_from_audit_record, action_from_audit_record] = Rule.parse_audit_record_params(
        record.params)
    assert record.type == mediaserver.api.audit_trail_events.EVENT_RULE_REMOVE
    assert event_from_audit_record == event_type
    assert action_from_audit_record == action.type
    assert not mediaserver.api.get_event_rule(rule_id)
