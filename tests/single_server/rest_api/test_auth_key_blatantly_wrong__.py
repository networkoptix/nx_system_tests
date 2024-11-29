# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import base64

import requests

from ca import default_ca
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_auth_key_blatantly_wrong(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    api = one_mediaserver.mediaserver().api
    api.setup_local_system()
    nonce_realm_url = api.http_url('api/getNonce')
    nonce_realm_response = requests.get(nonce_realm_url, verify=default_ca().cert_path)
    nonce_realm_data = nonce_realm_response.json()
    nonce = nonce_realm_data['reply']['nonce']
    auth_digest = base64.b64encode(b'admin:' + nonce.encode() + b':wrong')
    url = api.http_url('api/systemSettings')
    response = requests.get(
        url, params={'auth': auth_digest}, verify=default_ca().cert_path)
    assert response.status_code == 401
