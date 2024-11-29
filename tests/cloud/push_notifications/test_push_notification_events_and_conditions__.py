# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from cloud_api.cloud import make_cloud_account_factory
from cloud_api.cloud import make_push_notification_viewer
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import EventState
from mediaserver_api import EventType
from mediaserver_api import RuleAction
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.cloud.push_notifications.conftest import configure_for_push_notifications


def _test_initiate_push_notification(cloud_host, distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    push_notification_viewer = make_push_notification_viewer(cloud_host)
    cloud_account_factory = make_cloud_account_factory(cloud_host)
    cloud_account = cloud_account_factory.create_account()
    customization_name = installer_supplier.distrib().customization().customization_name
    cloud_account.set_user_customization(customization_name)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    cloud_mediaserver = one_mediaserver.mediaserver()
    configure_for_push_notifications(cloud_mediaserver, cloud_host, cloud_account)
    api = cloud_mediaserver.api
    [cloud_user] = [u for u in api.list_users() if u.is_cloud]
    api.add_event_rule(
        event_type=EventType.USER_DEFINED,
        event_state=EventState.UNDEFINED,
        action=RuleAction.push_notification([cloud_user.id]))
    cloud_system_id = api.get_cloud_system_id()
    with push_notification_viewer.wait_for_new_notifications(cloud_system_id):
        api.create_event(caption='irrelevant')
    [notification] = push_notification_viewer.new_notifications
    [target_user_email] = notification.raw_targets
    assert cloud_user.email == target_user_email
    assert notification.raw_system_id == cloud_system_id
    cloud_mediaserver.block_access_to_cloud(cloud_host)
    notification_count = 5
    with push_notification_viewer.ensure_no_notifications_received(
            cloud_system_id, silence_period_sec=20):
        for _ in range(notification_count):
            api.create_event(caption='irrelevant')
            time.sleep(1)  # Pause for a second, real life events occur with pause as well.
    with push_notification_viewer.wait_for_new_notifications(
            cloud_system_id, timeout_sec=60, expected_notification_count=notification_count):
        cloud_mediaserver.allow_access_to_cloud(cloud_host)
    actual_notification_count = len(push_notification_viewer.new_notifications)
    assert actual_notification_count == notification_count
    # Ensure no unexpected notifications appear after internet is enabled again.
    with push_notification_viewer.ensure_no_notifications_received(
            cloud_system_id, silence_period_sec=10):
        pass
    system_name = api.get_system_name()
    password = 'Irrelevant123'
    api.detach_from_cloud(password, cloud_account.password)
    if api_version == 'v0':
        # Admin settings are reset after disconnecting the system from the cloud.
        # Therefore, Basic and Digest authentication should be re-enabled.
        api.enable_basic_and_digest_auth_for_admin()
    assert api.is_online()
    with push_notification_viewer.ensure_no_notifications_received(
            cloud_system_id, silence_period_sec=20):
        api.create_event(caption='irrelevant')
    bind_info = cloud_account.bind_system(system_name)
    api.connect_system_to_cloud(
        bind_info.auth_key, bind_info.system_id, cloud_account.user_email)
    cloud_system_id = api.get_cloud_system_id()
    with push_notification_viewer.wait_for_new_notifications(cloud_system_id):
        api.create_event(caption='irrelevant')
    [notification] = push_notification_viewer.new_notifications
    [target_user_email] = notification.raw_targets
    assert cloud_user.email == target_user_email
