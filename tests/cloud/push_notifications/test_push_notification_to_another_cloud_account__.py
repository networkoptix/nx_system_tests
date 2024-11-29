# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from cloud_api.cloud import make_cloud_account_factory
from cloud_api.cloud import make_push_notification_viewer
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import EventState
from mediaserver_api import EventType
from mediaserver_api import RuleAction
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.cloud.push_notifications.conftest import configure_for_push_notifications


def _test_reconnect_to_another_cloud_account(cloud_host, distrib_url, one_vm_type, api_version, all_users, exit_stack):
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
    first_email = cloud_account.user_email
    first_system_id = api.get_cloud_system_id()
    if all_users:
        action = RuleAction.push_notification_all_users()
    else:
        action = RuleAction.push_notification([cloud_user.id])
    api.add_event_rule(
        event_type=EventType.USER_DEFINED,
        event_state=EventState.UNDEFINED,
        action=action)
    with push_notification_viewer.wait_for_new_notifications(first_system_id):
        api.create_event(caption='irrelevant')
    [notification] = push_notification_viewer.new_notifications
    assert notification.raw_system_id == first_system_id
    assert notification.raw_targets == [first_email]
    system_name = api.get_system_name()
    password = 'Irrelevant123'
    api.detach_from_cloud(password, cloud_account.password)
    if api_version == 'v0':
        # Admin settings are reset after disconnecting the system from the cloud.
        # Therefore, Basic and Digest authentication should be re-enabled.
        api.enable_basic_and_digest_auth_for_admin()
    assert api.is_online()
    second_cloud_account = cloud_account_factory.create_account()
    second_cloud_account.set_user_customization(customization_name)
    second_email = second_cloud_account.user_email
    bind_info = second_cloud_account.bind_system(system_name)
    api.connect_system_to_cloud(bind_info.auth_key, bind_info.system_id, second_email)
    second_system_id = api.get_cloud_system_id()
    if all_users:
        with push_notification_viewer.wait_for_new_notifications(second_system_id):
            api.create_event(caption='irrelevant')
        [notification] = push_notification_viewer.new_notifications
        assert notification.raw_system_id == second_system_id
        assert notification.raw_targets == [second_email]
    else:
        with push_notification_viewer.ensure_no_notifications_received(
                second_system_id, silence_period_sec=20):
            api.create_event(caption='irrelevant')
