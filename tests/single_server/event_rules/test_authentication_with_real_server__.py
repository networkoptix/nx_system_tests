# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import urllib.parse
from ipaddress import ip_network

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import HttpAction
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.single_server.event_rules.common import event


def _test_authentication_with_real_server(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    two_mediaservers.start()
    two_mediaservers.setup_system()
    one = two_mediaservers.first.installation()
    two = two_mediaservers.second.installation()
    remote_ip = two.api.list_ip_addresses()
    accessible_ip_net = ip_network('10.254.0.0/16')
    try:
        remote_ip = next(ip for ip in remote_ip if ip in accessible_ip_net)
    except StopIteration:
        raise RuntimeError(
            "Second server is unable to see first server: none of interfaces "
            f"{remote_ip} of {two} are in network {accessible_ip_net}",
            )
    event_queue = two.api.event_queue()
    event_queue.skip_existing_events()
    caption_expected = 'Event created by HTTP request from first server'
    credentials = two.api.get_credentials()
    netloc = f'{credentials.username}:{credentials.password}@{remote_ip}:{two.port}'
    url = urllib.parse.urlunsplit((
        'http',
        netloc,
        '/api/createEvent',
        'caption=' + urllib.parse.quote(caption_expected),
        None,
        ))
    with event(one.api, HttpAction(url, {'authType': 'authDigest'})):
        caption = event_queue.wait_for_next().caption
        assert caption == caption_expected, f"Unexpected caption: {caption!r}"
    with event(one.api, HttpAction(url, {'authType': 'authBasic'})):
        caption = event_queue.wait_for_next().caption
        assert caption == caption_expected, f"Unexpected caption: {caption!r}"
    with event(one.api, HttpAction(url, {'authType': 'authBasicAndDigest'})):
        caption = event_queue.wait_for_next().caption
        assert caption == caption_expected, f"Unexpected caption: {caption!r}"
    url = url.replace('http://', 'https://')
    with event(one.api, HttpAction(url, {'authType': 'authDigest'})):
        caption = event_queue.wait_for_next().caption
        assert caption == caption_expected, f"Unexpected caption: {caption!r}"
    with event(one.api, HttpAction(url, {'authType': 'authBasic'})):
        caption = event_queue.wait_for_next().caption
        assert caption == caption_expected, f"Unexpected caption: {caption!r}"
    with event(one.api, HttpAction(url, {'authType': 'authBasicAndDigest'})):
        caption = event_queue.wait_for_next().caption
        assert caption == caption_expected, f"Unexpected caption: {caption!r}"
