# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from typing import Sequence
from urllib.request import urlopen

from distrib._link_parser import parse_links

_logger = logging.getLogger(__name__)


def list_installers_url(installers_url_root: str) -> Sequence[str]:
    with urlopen(installers_url_root, timeout=3) as response:
        links = parse_links(installers_url_root, response)
    builds = []
    for link in links:
        if link == installers_url_root:
            continue
        if not link.startswith(installers_url_root):
            continue
        if not link.endswith('/'):
            continue
        builds.append(link.rstrip('/') + '/default/distrib/')
    return builds[::-1]


def list_distrib_files(installers_url: str) -> Sequence[str]:
    with urlopen(installers_url, timeout=5) as response:
        links = parse_links(installers_url, response)
    if not installers_url.endswith('/'):
        installers_url += '/'
    return [
        link[len(installers_url):]
        for link in links
        if link.startswith(installers_url) and not link == installers_url
        ]
