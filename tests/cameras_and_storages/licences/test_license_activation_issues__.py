# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from datetime import date

from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from installation import ClassicInstallerSupplier
from mediaserver_api import LicenseAddError
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_license_activation_issues(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.allow_license_server_access(license_server.url())
    mediaserver.api.set_license_server(license_server.url())

    # In APIv1, the key is part of the URL, so it cannot be omitted
    if api_version != 'v1':
        try:
            mediaserver.api.activate_license('')
        except LicenseAddError as e:
            assert e.error_id == 'missingParameter'
        else:
            raise Exception("Did not raise")

    wrong_key = 'WRONG_LICENSE_KEY'
    try:
        mediaserver.api.activate_license(wrong_key)
    except Exception as e:
        assert "serial number must be in format aaaa-bbbb-cccc-dddd" in str(e).lower()
    else:
        raise Exception("Did not raise")

    brand = mediaserver.api.get_brand()
    expired_key = license_server.generate({
        'BRAND2': brand,
        'FIXED_EXPIRATION_TS': date(2020, 1, 1).strftime('%m/%d/%Y'),
        })
    try:
        mediaserver.api.activate_license(expired_key)
    except Exception as e:
        assert "license is expired" in str(e).lower()
    else:
        raise Exception("Did not raise")

    key = license_server.generate({'BRAND2': brand})
    mediaserver.block_license_server_access(license_server.url())
    try:
        mediaserver.api.activate_license(key)
    except Exception as e:
        assert "error has occurred during license activation" in str(e).lower()
    else:
        raise Exception("Did not raise")
