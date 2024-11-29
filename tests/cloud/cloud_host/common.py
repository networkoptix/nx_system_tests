# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
def check_user_exists(server, is_cloud):
    users = server.api.list_users()
    credentials = server.api.get_credentials()
    cloud_users = [u for u in users if u.name == credentials.username]
    assert len(cloud_users) == 1  # One cloud user is expected
    assert cloud_users[0].is_enabled
    assert cloud_users[0].is_cloud == is_cloud
    if not is_cloud:
        assert len(users) == 1  # No other users are expected for locally setup server
