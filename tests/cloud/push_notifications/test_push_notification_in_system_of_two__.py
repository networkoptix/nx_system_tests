# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json

from cloud_api.cloud import make_cloud_account_factory
from cloud_api.cloud import make_push_notification_viewer
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import public_ip_check_addresses
from mediaserver_api import EventCondition
from mediaserver_api import EventState
from mediaserver_api import EventType
from mediaserver_api import RuleAction
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.cloud.push_notifications.conftest import disable_camera_disconnected_push
from tests.cloud.push_notifications.conftest import force_early_server_start_event


def _test_system(cloud_host, distrib_url, two_vm_types, internet_enabled_on_second, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    push_notification_viewer = make_push_notification_viewer(cloud_host)
    cloud_account_factory = make_cloud_account_factory(cloud_host)
    cloud_account = cloud_account_factory.create_account()
    customization_name = installer_supplier.distrib().customization().customization_name
    cloud_account.set_user_customization(customization_name)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    first = two_mediaservers.first.installation()
    second = two_mediaservers.second.installation()
    force_early_server_start_event(first)
    force_early_server_start_event(second)
    second.os_access.cache_dns_in_etc_hosts([cloud_host, *public_ip_check_addresses])
    if internet_enabled_on_second:
        second.allow_access_to_cloud(cloud_host)
    second.set_cloud_host(cloud_host)
    first.os_access.cache_dns_in_etc_hosts([cloud_host, *public_ip_check_addresses])
    first.allow_access_to_cloud(cloud_host)
    first.set_cloud_host(cloud_host)
    first.start()
    first.api.setup_cloud_system(cloud_account)
    disable_camera_disconnected_push(first.api)
    second.start()
    second.api.setup_local_system()
    merge_systems(first, second, take_remote_settings=False)
    [cloud_user] = [u for u in first.api.list_users() if u.is_cloud]
    first_caption = "FirstCaption"
    [first_camera_ids] = first.api.add_test_cameras(offset=0, count=1)
    first_camera_id = str(first_camera_ids.id)
    first.api.add_event_rule(
        event_type=EventType.USER_DEFINED,
        event_state=EventState.UNDEFINED,
        action=RuleAction.push_notification([cloud_user.id]),
        event_condition=EventCondition(params={'caption': first_caption}),
        event_resource_ids=[first_camera_id])
    second_caption = "SecondCaption"
    [second_camera_ids] = second.api.add_test_cameras(offset=1, count=1)
    second_camera_id = str(second_camera_ids.id)
    second.api.add_event_rule(
        event_type=EventType.USER_DEFINED,
        event_state=EventState.UNDEFINED,
        action=RuleAction.push_notification([cloud_user.id]),
        event_condition=EventCondition(params={'caption': second_caption}),
        event_resource_ids=[second_camera_id])
    cloud_system_id = first.api.get_cloud_system_id()
    with push_notification_viewer.wait_for_new_notifications(cloud_system_id):
        first.api.create_event(
            caption=first_caption, metadata=json.dumps({'cameraRefs': [first_camera_id]}))
    [first_notification] = push_notification_viewer.new_notifications
    assert first_notification.title == first_caption
    with push_notification_viewer.wait_for_new_notifications(cloud_system_id):
        second.api.create_event(
            caption=second_caption, metadata=json.dumps({'cameraRefs': [second_camera_id]}))
    [second_notification] = push_notification_viewer.new_notifications
    assert second_notification.title == second_caption
