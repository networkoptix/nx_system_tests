# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from uuid import uuid4

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import EventState
from mediaserver_api import EventType
from mediaserver_api import RuleAction
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_get_url(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    # Test that server receives own HTTP request (event rule action).
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver = one_mediaserver.mediaserver()
    events = mediaserver.api.event_queue()
    events.skip_existing_events()
    mediaserver.api.disable_event_rules()
    [camera] = mediaserver.api.add_test_cameras(offset=0, count=1)
    action_event_source = str(uuid4())
    credentials = mediaserver.api.get_credentials()
    url = (
        f"http://{credentials.username}:{credentials.password}@127.0.0.1:{mediaserver.port}"
        f"/api/createEvent?source={action_event_source}")
    action = RuleAction.http_request(url)
    camera_motion_rule_id = mediaserver.api.add_event_rule(
        event_type=EventType.CAMERA_MOTION,
        event_state=EventState.ACTIVE,
        action=action,
        )
    user_defined_rule_id = mediaserver.api.add_event_rule(
        event_type=EventType.USER_DEFINED,
        event_state=EventState.UNDEFINED,
        action=RuleAction('showPopupAction'),
        )
    camera_motion_event_source = str(uuid4())
    mediaserver.api.create_event(
        event_type=EventType.CAMERA_MOTION,
        eventResourceId=str(camera.id),
        state=EventState.ACTIVE,
        source=camera_motion_event_source,
        )
    http_request_event = events.wait_for_next()
    assert http_request_event.action_type == action.type
    assert http_request_event.rule_id == camera_motion_rule_id
    assert http_request_event.action_url == url
    assert http_request_event.resource_id == camera.id
    assert http_request_event.event_type == EventType.CAMERA_MOTION

    user_defined_event = events.wait_for_next()
    assert user_defined_event.action_type == 'showPopupAction'
    assert user_defined_event.rule_id == user_defined_rule_id
    assert user_defined_event.event_type == EventType.USER_DEFINED
    assert user_defined_event.resource_name == action_event_source
