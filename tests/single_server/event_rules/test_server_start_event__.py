# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from datetime import timedelta

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import EventState
from mediaserver_api import EventType
from mediaserver_api import RuleAction
from mediaserver_api import RuleActionType
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_server_start_event(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    # There is system event rule for that already, disable it among all other rules.
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    api = one_mediaserver.mediaserver().api
    api.disable_event_rules()
    start_event_type = EventType.SERVER_START
    action_type = RuleActionType.DIAGNOSTIC
    api.add_event_rule(
        event_type=start_event_type,
        event_state=EventState.UNDEFINED,
        action=RuleAction(action_type))
    event_queue = api.event_queue()
    event_queue.skip_existing_events()
    api.restart()
    record = event_queue.wait_for_next()
    server_current_time = api.get_datetime()
    assert server_current_time - record.event_date < timedelta(seconds=2)
    assert record.event_type == start_event_type
    assert record.action_type == action_type
