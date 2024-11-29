# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from datetime import datetime

import requests


def get_hls_start_datetime(url, ca) -> datetime:
    response = requests.get(url, params={'chunked': True}, verify=ca.cert_path, timeout=30)
    tag = 'EXT-X-PROGRAM-DATE-TIME'
    for line in response.text.splitlines():
        if tag in line:
            [_, value] = line.split(':', maxsplit=1)
            return datetime.fromisoformat(value)
    raise RuntimeError(f"There is no {tag} tag in playlist.")
