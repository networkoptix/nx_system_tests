# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
from functools import partial

from cloud_api.cloud import make_cloud_account_factory
from cloud_api.cloud import make_push_notification_viewer
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import EventState
from mediaserver_api import EventType
from mediaserver_api import RuleAction
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.cloud.push_notifications.conftest import configure_for_push_notifications


def _test_push_notification_text(cloud_host, distrib_url, one_vm_type, api_version, exit_stack):
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
    cloud_system_id = api.get_cloud_system_id()
    [camera_ids] = api.add_test_cameras(offset=0, count=1)
    camera = api.get_camera(camera_ids.id)
    check_fn = partial(
        _check_push_notification,
        api,
        push_notification_viewer,
        cloud_system_id,
        cloud_user.id,
        camera)
    check_fn(
        event_caption='event_caption',
        event_source='event_source',
        event_description='event_description')
    check_fn(
        event_caption='event_caption',
        event_source='event_source',
        event_description='event_description',
        add_device_name=True)
    check_fn(
        event_caption='event_caption',
        event_source='event_source',
        event_description='event_description',
        notification_title='notification_title',
        notification_description='notification_description')
    check_fn(
        event_caption='event_caption',
        event_source='event_source',
        event_description='event_description',
        notification_title='notification_title',
        notification_description='notification_description',
        add_device_name=True)
    check_fn(event_caption='event_caption')
    check_fn(event_caption='event_caption', event_source='event_source')
    check_fn(event_source='event_source', event_description='event_description')
    check_fn(event_source='event_source')


def _check_push_notification(
        api,
        push_notification_viewer,
        cloud_system_id,
        cloud_user_id,
        camera,
        event_caption=None,
        event_source=None,
        event_description=None,
        notification_title=None,
        notification_description=None,
        add_device_name=False):
    rule_id = api.add_event_rule(
        event_type=EventType.USER_DEFINED,
        event_state=EventState.UNDEFINED,
        action=RuleAction.push_notification(
            [cloud_user_id],
            title=notification_title,
            description=notification_description,
            add_device_name=add_device_name))
    event_params = {
        'caption': event_caption,
        'source': event_source,
        'description': event_description,
        'metadata': json.dumps({'cameraRefs': [str(camera.id)]}),
        }
    with push_notification_viewer.wait_for_new_notifications(cloud_system_id):
        # Filter out None values, because otherwise it will be sent into mediaserver.
        api.create_event(**{k: v for k, v in event_params.items() if v is not None})
    [notification] = push_notification_viewer.new_notifications
    expected_title = notification_title or event_caption or 'Generic Event'
    expected_description = notification_description or event_description or ''
    assert notification.title == expected_title
    if add_device_name:
        assert expected_description in notification.body
        assert camera.name in notification.body
    else:
        assert notification.body == expected_description
    api.remove_event_rule(rule_id)
