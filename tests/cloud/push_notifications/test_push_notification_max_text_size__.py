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


def _test_max_notification_text_size(cloud_host, distrib_url, one_vm_type, api_version, exit_stack):
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
    title_symbol_limit = 100
    body_symbol_limit = 500
    api.add_event_rule(
        event_type=EventType.USER_DEFINED,
        event_state=EventState.UNDEFINED,
        action=RuleAction.push_notification(
            [cloud_user.id],
            title='t' * (title_symbol_limit + 1),
            description='b' * (body_symbol_limit + 1)))
    cloud_system_id = api.get_cloud_system_id()
    with push_notification_viewer.wait_for_new_notifications(cloud_system_id):
        api.create_event(source='irrelevant')
    [notification] = push_notification_viewer.new_notifications
    assert len(notification.title) == title_symbol_limit
    assert len(notification.body) == body_symbol_limit
