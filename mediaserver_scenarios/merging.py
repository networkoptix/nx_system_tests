# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from ipaddress import IPv4Address
from ipaddress import IPv4Network
from typing import Any
from typing import Mapping
from typing import Sequence

from installation import Mediaserver
from os_access import OsAccess
from os_access import PingError

_logger = logging.getLogger(__name__)
DEFAULT_ACCESSIBLE_IP_NET = IPv4Network('10.254.0.0/16')
DEFAULT_MERGE_TIMEOUT_SEC = 30


def _get_remote_address(
        local_os_access: OsAccess,
        remote_os_access: OsAccess,
        accessible_ip_net: IPv4Network,
        ) -> IPv4Address:
    remote_interfaces = remote_os_access.networking.get_ip_addresses_within_subnet(accessible_ip_net)
    if not remote_interfaces:
        raise RuntimeError("There is no common network")
    if len(remote_interfaces) >= 2:
        raise RuntimeError(
            f"{len(remote_interfaces)} common networks were found. Don't know which to choose")
    [remote_interface] = remote_interfaces
    remote_address = remote_interface.ip
    try:
        local_os_access.networking.ping(str(remote_address))
    except PingError:
        raise RuntimeError(f"{remote_address} is not reachable from {local_os_access}")
    return remote_address


def merge_many_servers(servers: Sequence[Mediaserver]):
    [local, *remotes] = servers
    _logger.info("Request %s to merge %s", local, remotes)
    remote_api_list = [s.api for s in remotes]
    accessible_ip_network = DEFAULT_ACCESSIBLE_IP_NET
    local.api.check_system_ids_before_merge(remote_api_list)
    remote_urls = []
    remote_auth_list = []
    # Prepare params for merge request first. Remote can be unreachable, there is no point in
    # merge request to unreachable server. Checking this before request will produce clear error
    # and error will occur faster.
    for remote in remotes:
        remote_address = _get_remote_address(
            local.os_access, remote.os_access, accessible_ip_network)
        remote_urls.append(f"https://{remote_address}:{remote.port}")
        remote_auth = remote.api.get_auth_data()
        remote_auth_list.append(remote_auth)
    merge_responses = []
    for remote_api, url, remote_auth in zip(remote_api_list, remote_urls, remote_auth_list):
        response = local.api.request_merge(url, remote_auth)
        merge_responses.append(response)
        remote_api.import_auth(local.api)
    local.api.wait_for_merge(remote_api_list, merge_responses)


def merge_systems(
        local: Mediaserver,  # Request will be sent to this.
        remote: Mediaserver,
        take_remote_settings,
        accessible_ip_net=DEFAULT_ACCESSIBLE_IP_NET,
        timeout_sec=DEFAULT_MERGE_TIMEOUT_SEC,
        merge_one_server=False,
        ):
    [master, servant] = [local, remote] if not take_remote_settings else [remote, local]
    _logger.info("Merging %s to %s", servant, master)
    master.api.check_system_ids_before_merge([servant.api])
    remote_address = _get_remote_address(local.os_access, remote.os_access, accessible_ip_net)
    remote_auth = remote.api.get_auth_data()
    merge_response = local.api.request_merge(
        f"https://{remote_address}:{remote.port}",
        remote_auth,
        take_remote_settings=take_remote_settings,
        merge_one_server=merge_one_server)
    servant.api.import_auth(master.api)
    master.api.wait_for_merge([servant.api], [merge_response], timeout_sec=timeout_sec)


def setup_system(mediaservers: Mapping[str, Mediaserver], scheme: Sequence[Mapping[str, Any]]):
    """Merge servers according to the scheme provided.

    Request is sent to "local".
    "Local" is asked to merge with the URL and the credentials of "remote".
    """
    for merger in scheme:
        merge_systems(
            mediaservers[merger['local']],
            mediaservers[merger['remote']],
            take_remote_settings=merger['take_remote_settings'],
            accessible_ip_net=IPv4Network(merger.get('network', DEFAULT_ACCESSIBLE_IP_NET)))
