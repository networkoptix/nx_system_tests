# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from flask import render_template

from infrastructure.ft_view import _db


def run_locations():
    users, hosts, locations = _users_hosts_locations()
    return render_template(
        'locations.html',
        users=users,
        hosts=hosts,
        locations=locations,
        )


def _users_hosts_locations():
    result = _db.select(
        'SELECT DISTINCT r.run_username, r.run_hostname FROM ('
        'SELECT run_username, run_hostname '
        'FROM run '
        'ORDER BY run_started_at DESC '
        'LIMIT 100000 '
        ') r '
        ';', {
            })
    users = sorted({row['run_username'] for row in result})
    hosts = sorted({row['run_hostname'] for row in result})
    locations = sorted(
        (row['run_username'], row['run_hostname'])
        for row in result)
    return users, hosts, locations
