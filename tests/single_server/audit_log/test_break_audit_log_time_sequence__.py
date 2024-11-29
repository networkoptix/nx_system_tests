# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import public_ip_check_addresses
from installation import time_server
from mediaserver_api import AuditTrail
from mediaserver_api import MediaserverApi
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.merged_systems.time_synchronization.running_time import wait_until_mediaserver_time_sync_with_internet


def _test_break_audit_log_time_sequence(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type)).mediaserver()
    mediaserver.os_access.set_datetime(datetime.now(timezone.utc) + timedelta(days=2))
    mediaserver.update_ini('nx_vms_server', {'publicIpDiscoveryIntervalMs': 2000})
    mediaserver.start()
    mediaserver.api.setup_local_system()
    mediaserver_time_before = mediaserver.api.get_datetime()
    started_at = time.monotonic()
    audit_trail = mediaserver.api.audit_trail()
    resource = _SomeResource(mediaserver.api, audit_trail)
    first_record = resource.create()
    first_event_at = datetime.fromtimestamp(float(first_record.created_time_sec), timezone.utc)
    mediaserver.api.set_system_settings({'syncTimeExchangePeriod': 5000})
    audit_trail.wait_for_one()
    mediaserver.os_access.cache_dns_in_etc_hosts([*public_ip_check_addresses, time_server])
    mediaserver.allow_time_server_access()
    wait_until_mediaserver_time_sync_with_internet(mediaserver.api, timeout_sec=180)
    elapsed_sec = time.monotonic() - started_at
    mediaserver_time_would_be = mediaserver_time_before + timedelta(seconds=elapsed_sec)
    assert mediaserver_time_would_be > mediaserver.api.get_datetime()
    # Second event with new time will break audit log time sequence.
    # After VMS-14327, audit log messages are not sorted by `createdTime`
    second_record = resource.change()
    second_event_at = datetime.fromtimestamp(float(second_record.created_time_sec), timezone.utc)
    # First event has created timestamp, it occurred before the time synchronization.
    assert first_event_at > second_event_at


class _SomeResource:
    """Resource whose type is irrelevant for the test.

    It does not matter what is created and what is changed.
    But Audit Trail record types matter.
    """

    def __init__(self, api: MediaserverApi, audit_trail: AuditTrail):
        self._api = api
        self._audit_trail = audit_trail
        self._id = None

    def create(self) -> AuditTrail.AuditRecord:
        assert self._id is None
        cameras = self._api.add_test_cameras(0, 1)
        self._id = cameras[0].id
        records = self._audit_trail.wait_for_sequence()
        assert records[0].type == self._api.audit_trail_events.CAMERA_INSERT
        assert records[0].resources == [self._id]
        if len(records) == 2:
            # There seems to be "insert" and "update" records on Ubuntu,
            # and only an "insert" record on Windows.
            # It makes no difference for the test though.
            assert records[1].type == self._api.audit_trail_events.CAMERA_UPDATE
            assert records[1].resources == [self._id]
        return records[0]

    def change(self) -> AuditTrail.AuditRecord:
        assert self._id is not None
        server_id = self._api.get_server_id()
        self._api.set_camera_preferred_parent(self._id, server_id)
        record = self._audit_trail.wait_for_one()
        assert record.type == self._api.audit_trail_events.CAMERA_UPDATE
        assert record.resources == [self._id]
        return record
