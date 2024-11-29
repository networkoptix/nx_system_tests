# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time

from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import public_ip_check_addresses
from mediaserver_api import AuditTrail
from mediaserver_api import EventNotOccurred
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def raise_at_unauthorized_login(audit_trail: AuditTrail, timeout_sec: float):
    now = time.monotonic()
    end_at = now + timeout_sec
    while True:
        audit_trail_timeout = end_at - now
        if audit_trail_timeout < 0:
            logging.info("There is no time left to wait for a next event")
            break
        logging.info("Wait an event for %s seconds", audit_trail_timeout)
        try:
            event = audit_trail.wait_for_next(timeout_sec=audit_trail_timeout)
        except EventNotOccurred:
            break
        now = time.monotonic()
        if event == 'AR_UnauthorizedLogin':
            raise AssertionError('Received AR_UnauthorizedLogin event')
        logging.info("Received event %s", event)
    logging.info("Has not received AR_UnauthorizedLogin after %s seconds", timeout_sec)


def _test_connect_disconnect(cloud_host, distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    cloud_account_factory = make_cloud_account_factory(cloud_host)
    cloud_account = cloud_account_factory.create_account()
    customization_name = installer_supplier.distrib().customization().customization_name
    cloud_account.set_user_customization(customization_name)
    # The v0 auth scheme is disabled by default for queries used by the test.
    # Enabling it causes extra records in the audit trail and breaks the test
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.os_access.cache_dns_in_etc_hosts([cloud_host, *public_ip_check_addresses])
    mediaserver.allow_access_to_cloud(cloud_host)
    mediaserver.set_cloud_host(cloud_host)
    mediaserver.start()
    mediaserver.api.setup_local_system()
    audit_trail = mediaserver.api.audit_trail()
    bind_info = cloud_account.bind_system(system_name='Irrelevant')
    mediaserver.api.connect_system_to_cloud(
        bind_info.auth_key, bind_info.system_id, cloud_account.user_email)
    raise_at_unauthorized_login(audit_trail, timeout_sec=10)
    mediaserver.api.detach_from_cloud(cloud_account.password, cloud_account.password)
    raise_at_unauthorized_login(audit_trail, timeout_sec=10)
