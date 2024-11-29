# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import requests
from requests.auth import HTTPDigestAuth

from ca import default_ca
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_non_existent_api_endpoints(distrib_url, one_vm_type, path, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver = one_mediaserver.mediaserver()
    credentials = mediaserver.api.get_credentials()
    auth = HTTPDigestAuth(credentials.username, credentials.password)
    response = requests.get(
        mediaserver.api.http_url(path),
        auth=auth,
        allow_redirects=False,
        verify=default_ca().cert_path,
        )
    assert response.status_code == 404
