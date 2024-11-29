# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json

from cloud_api.cloud import make_cloud_account_factory
from cloud_api.cloud import make_push_notification_viewer
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import public_ip_check_addresses
from mediaserver_api import EventState
from mediaserver_api import EventType
from mediaserver_api import Permissions
from mediaserver_api import RuleAction
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.cloud.push_notifications.conftest import disable_camera_disconnected_push
from tests.cloud.push_notifications.conftest import force_early_server_start_event


def _test_cloud_user_without_permissions(cloud_host, distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    distrib = installer_supplier.distrib()
    push_notification_viewer = make_push_notification_viewer(cloud_host)
    cloud_account_factory = make_cloud_account_factory(cloud_host)
    cloud_account = cloud_account_factory.create_account()
    customization_name = distrib.customization().customization_name
    cloud_account.set_user_customization(customization_name)
    distrib.assert_api_support(api_version, 'users')
    second_cloud_account = cloud_account_factory.create_account()
    second_cloud_account.set_user_customization(customization_name)
    second_email = second_cloud_account.user_email
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.os_access.cache_dns_in_etc_hosts([cloud_host, *public_ip_check_addresses])
    mediaserver.allow_access_to_cloud(cloud_host)
    mediaserver.set_cloud_host(cloud_host)
    force_early_server_start_event(mediaserver)
    mediaserver.start()
    api = one_mediaserver.api()
    api.setup_cloud_system(cloud_account)
    disable_camera_disconnected_push(mediaserver.api)
    group_id = api.add_user_group('irrelevant', [Permissions.NO_GLOBAL])
    second_cloud_user_id = api.add_cloud_user(
        second_email,
        group_id=group_id,
        email=second_email,
        )
    rule_id = api.add_event_rule(
        event_type=EventType.USER_DEFINED,
        event_state=EventState.UNDEFINED,
        action=RuleAction.push_notification([second_cloud_user_id]))
    [camera] = api.add_test_cameras(offset=0, count=1)
    logical_id = 1
    api.set_camera_logical_id(camera.id, logical_id)
    id_metadata = json.dumps({'cameraRefs': [str(camera.id)]})
    physical_id_metadata = json.dumps({'cameraRefs': [camera.physical_id]})
    logical_id_metadata = json.dumps({'cameraRefs': [str(logical_id)]})
    cloud_system_id = api.get_cloud_system_id()
    with push_notification_viewer.ensure_no_notifications_received(
            cloud_system_id, silence_period_sec=10):
        api.create_event(caption='irrelevant', metadata=id_metadata)
        api.create_event(caption='irrelevant', metadata=physical_id_metadata)
        api.create_event(caption='irrelevant', metadata=logical_id_metadata)
    api.set_event_rule_action(rule_id, RuleAction.push_notification_all_users())
    with push_notification_viewer.wait_for_new_notifications(
            cloud_system_id, expected_notification_count=3):
        api.create_event(caption='irrelevant', metadata=id_metadata)
        api.create_event(caption='irrelevant', metadata=physical_id_metadata)
        api.create_event(caption='irrelevant', metadata=logical_id_metadata)
    first_email = cloud_account.user_email
    assert all(n.raw_targets == [first_email] for n in push_notification_viewer.new_notifications)
