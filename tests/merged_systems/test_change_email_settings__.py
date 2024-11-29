# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_change_email_settings(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    server = one_mediaserver.mediaserver()
    audit_trail = server.api.audit_trail()
    audit_trail.skip_existing_events()
    email = 'arbitrary.user@example.org'
    server.api.set_email_settings(email=email)
    assert server.api.get_email_settings().email == email
    email = 'Arbitrary Name <user@nx.com>'
    server.api.set_email_settings(email=email)
    assert server.api.get_email_settings().email == email
    signature = 'arbitrary_signature'
    server.api.set_email_settings(signature=signature)
    assert server.api.get_email_settings().signature == signature
    support_address = 'user@nx.com'
    server.api.set_email_settings(support_address=support_address)
    assert server.api.get_email_settings().support_address == support_address
    support_address = 'Arbitrary Name <u@nx.org>'
    server.api.set_email_settings(support_address=support_address)
    assert server.api.get_email_settings().support_address == support_address
    records = audit_trail.wait_for_sequence()
    record_types = [record.type for record in records]
    assert record_types == [server.api.audit_trail_events.EMAIL_SETTINGS] * 5
