# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from installation import public_ip_check_addresses
from mediaserver_api import EventType


def disable_camera_disconnected_push(server_api):
    for rule in server_api.list_event_rules():
        if (rule.event, rule.action) == (EventType.CAMERA_DISCONNECT, 'pushNotificationAction'):
            server_api.disable_event_rule(rule.id)
            return
    raise RuntimeError(
        "There is no rule to send a push notification when the camera is disconnected. "
        "Make sure that the format of the rule has not changed")


def force_early_server_start_event(mediaserver):
    # Reduce serverStartedEventTimeoutMs to force the server to send the EventType.SERVER_START
    # event earlier. Thus, these events won't appear during tests and won't cause tests to fail.
    mediaserver.update_conf({'serverStartedEventTimeoutMs': 100})


def configure_for_push_notifications(mediaserver, cloud_host, cloud_account):
    mediaserver.os_access.cache_dns_in_etc_hosts([cloud_host, *public_ip_check_addresses])
    mediaserver.allow_access_to_cloud(cloud_host)
    mediaserver.set_cloud_host(cloud_host)
    force_early_server_start_event(mediaserver)
    mediaserver.start()
    mediaserver.api.setup_cloud_system(cloud_account)
    disable_camera_disconnected_push(mediaserver.api)
