# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time


def make_session_old(server):
    credentials = server.api.get_credentials()
    session_info = server.api.get_session_info(credentials.token)
    current_session_age_sec = session_info.age_sec
    new_remaining_time_sec = 5
    server.update_ini('nx_network_rest', {
        'maxSessionAgeForPrivilegedApiS': current_session_age_sec + new_remaining_time_sec,
        })
    server.api.restart()
    # Wait until session is old enough to be unusable for privileged APIs.
    time.sleep(new_remaining_time_sec)
