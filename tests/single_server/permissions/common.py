# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from typing import Literal

from mediaserver_api import Permissions

USER_PERMISSIONS = {
    'admin': [Permissions.ADMIN],
    'viewer': Permissions.VIEWER_PRESET,
    'live_viewer': [Permissions.ACCESS_ALL_MEDIA],
    'advanced_viewer': Permissions.ADVANCED_VIEWER_PRESET,
    }


def get_api_for_actor(
        mediaserver_api,
        actor: Literal['admin', 'viewer', 'live_viewer', 'advanced_viewer'],
        ):
    username = 'test_' + actor
    actor = mediaserver_api.add_local_user(username, 'WellKnownPassword2', USER_PERMISSIONS[actor])
    actor_api = mediaserver_api.as_user(actor)
    return actor_api
