# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import EventNotOccurred
from mediaserver_api import EventState
from mediaserver_api import EventType
from mediaserver_api import HttpAction
from mediaserver_api import RuleAction
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.infra import assert_raises

_logger = logging.getLogger(__name__)


def _test_get_with_wrong_credentials(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver = one_mediaserver.mediaserver()
    server_guid = mediaserver.api.get_server_id()
    events = mediaserver.api.event_queue()
    events.skip_existing_events()
    mediaserver.api.disable_event_rules()
    url = (
        f'http://incorrect_user:incorrect_password@127.0.0.1:{mediaserver.port}'
        '/api/createEvent?caption=Event+created+by+HTTP+request')
    action = HttpAction(url)
    # The test creates event by itself, so we can use existent event type here.
    # Do not use camera events, because it can lead to get unexpected camera
    # disconnect events.
    mediaserver.api.add_event_rule(
        event_type=EventType.SERVER_FAILURE,
        event_state=EventState.UNDEFINED,
        action=action,
        )
    # Create user defined event rule to make sure event with wrong
    # credentials will not occur.
    mediaserver.api.add_event_rule(
        event_type=EventType.USER_DEFINED,
        event_state=EventState.UNDEFINED,
        action=RuleAction('diagnosticsAction'),
        )
    mediaserver.api.create_event(
        event_type=EventType.SERVER_FAILURE,
        eventResourceId=str(server_guid),
        state=EventState.ACTIVE,
        )
    event = events.wait_for_next()
    assert event.action_url == url
    assert event.action_type == action.type
    assert event.resource_id == server_guid
    assert event.event_type == EventType.SERVER_FAILURE

    with assert_raises(EventNotOccurred):
        # There is no other events - HTTP request event hasn't created
        # due to wrong credentials in the execHttpRequestAction's url.
        events.wait_for_next(timeout_sec=1)
