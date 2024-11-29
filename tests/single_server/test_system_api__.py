# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_system_settings(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    api = one_mediaserver.mediaserver().api
    new_system_name = 'new-system-name'
    api.rename_site(new_system_name)
    system_name = api.get_system_settings()['systemName']
    assert system_name == new_system_name
    email_from = 'arbitrary.user@example.org'
    email_support = 'arbitrary.user@example.org'
    api.set_email_settings(email=email_from, support_address=email_support)
    email_settings = api.get_email_settings()
    assert email_settings.email == email_from
    assert email_settings.support_address == email_support
    api.set_system_settings({'autoDiscoveryEnabled': 'false'})
    auto_discovery = api.get_system_settings()['autoDiscoveryEnabled']
    assert auto_discovery == 'false'
