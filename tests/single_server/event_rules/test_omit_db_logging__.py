# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import functools
import time

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import EventCondition
from mediaserver_api import EventNotOccurred
from mediaserver_api import EventState
from mediaserver_api import EventType
from mediaserver_api import RuleAction
from mediaserver_api import RuleActionType
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.waiting import wait_for_truthy


def _test_omit_db_logging(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver_api = one_mediaserver.mediaserver().api

    for event_rule in mediaserver_api.list_event_rules():
        if event_rule.event == EventType.USER_DEFINED:
            mediaserver_api.remove_event_rule(event_rule.id)

    event_queue = mediaserver_api.event_queue()
    event_queue.skip_existing_events()
    mediaserver_api.disable_event_rules()

    for omit_logging in (False, True):
        # When logging is NOT omitted - event should occur in logs.
        # When logging is omitted - no event should occur in logs.
        rule_id = mediaserver_api.add_event_rule(
            event_type=EventType.USER_DEFINED,
            event_state=EventState.UNDEFINED,
            action=RuleAction(RuleActionType.SHOW_POPUP, params={"allUsers": True}),
            event_condition=EventCondition(omit_db_logging=omit_logging))

        source = "Event source"
        check_event_func = functools.partial(
            _is_event_rule_working,
            mediaserver_api,
            event_queue,
            source,
            not omit_logging,
            )
        wait_for_truthy(check_event_func, description="Event rule works")
        # Try couple more times to see, if rule actually works
        time.sleep(5)
        assert check_event_func()

        mediaserver_api.remove_event_rule(rule_id)


def _is_event_rule_working(mediaserver_api, event_queue, source, should_occur):
    mediaserver_api.create_event(source=source)

    try:
        event = event_queue.wait_for_next(timeout_sec=5)
    except EventNotOccurred:
        event = None

    assert not event or event.resource_name == source
    return bool(event) == should_occur
