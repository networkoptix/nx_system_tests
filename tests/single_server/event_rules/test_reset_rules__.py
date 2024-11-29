# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from distrib import BranchNotSupported
from installation import ClassicInstallerSupplier
from mediaserver_api import EventState
from mediaserver_api import EventType
from mediaserver_api import Rule
from mediaserver_api import RuleAction
from mediaserver_api import RuleActionType
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_reset_rules(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver = one_mediaserver.mediaserver()
    branch = mediaserver.branch()
    if branch.startswith('mobile_'):
        raise BranchNotSupported(f"Branch {branch} is missing VMS-30117 fix.")
    audit_trail = mediaserver.api.audit_trail()
    rules_after_start = mediaserver.api.list_event_rules()
    event_type = EventType.CAMERA_DISCONNECT
    event_state = EventState.UNDEFINED
    action = RuleActionType.SHOW_TEXT_OVERLAY
    custom_rule_id = mediaserver.api.add_event_rule(
        event_type=event_type,
        event_state=event_state,
        action=RuleAction(action),
        )
    custom_rule = mediaserver.api.get_event_rule(custom_rule_id)
    rules_after_update = mediaserver.api.list_event_rules()
    mediaserver.api.reset_event_rules()
    rules_after_reset = mediaserver.api.list_event_rules()

    # Custom rules goes: absent -> existing -> removed.
    # Default rules goes: existing -> removed -> restored.
    rule_states = {}
    rule_states_expected = {}
    for rule in rules_after_start:
        rule_states[rule.event, rule.action] = 'existing'
        rule_states_expected[rule.event, rule.action] = 'restored'
    rule_states[custom_rule.event, custom_rule.action] = 'absent'
    rule_states_expected[custom_rule.event, custom_rule.action] = 'removed'
    record_list = audit_trail.wait_for_sequence()

    for record in record_list:
        [event, action] = Rule.parse_audit_record_params(record.params)
        if record.type == mediaserver.api.audit_trail_events.EVENT_RULE_REMOVE:
            assert rule_states[event, action] == 'existing'
            rule_states[event, action] = 'removed'
        elif record.type == mediaserver.api.audit_trail_events.EVENT_RULE_UPDATE:
            if (event, action) == (custom_rule.event, custom_rule.action):
                assert rule_states[event, action] == 'absent'
                rule_states[event, action] = 'existing'
            else:
                assert rule_states[event, action] == 'removed'
                rule_states[event, action] = 'restored'

    assert rule_states == rule_states_expected
    assert rules_after_start != rules_after_update
    assert rules_after_start == rules_after_reset
