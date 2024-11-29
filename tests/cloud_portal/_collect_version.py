# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from cloud_api.cloud import http_request
from cloud_api.cloud import make_cloud_certs_path
from directories import get_run_dir


def collect_version(cloud_host: str) -> None:
    response = http_request(
        method='GET',
        url=f'https://{cloud_host}/static/version.txt',
        ca_cert=str(make_cloud_certs_path(cloud_host)),
        )
    text = response.content.decode('utf-8')
    (get_run_dir() / 'cloud_version.txt').write_text(text)
