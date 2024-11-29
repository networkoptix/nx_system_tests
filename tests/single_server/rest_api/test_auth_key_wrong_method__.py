# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import requests

from ca import default_ca
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_auth_key_wrong_method(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    api = one_mediaserver.api()
    api.setup_local_system()
    response = requests.get(
        api.http_url('api/systemSettings'),
        params={'auth': api.auth_key('WRONG')},
        verify=default_ca().cert_path,
        )
    assert response.status_code == 401
