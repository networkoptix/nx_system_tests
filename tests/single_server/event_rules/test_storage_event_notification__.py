# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import textwrap

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import EventNotOccurred
from mediaserver_api import EventState
from mediaserver_api import EventType
from mediaserver_api import RuleAction
from mediaserver_api import RuleActionType
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from os_access._powershell import PowershellError
from os_access._powershell import run_powershell_script
from os_access._winrm_shell import WinRMShell

CORRECT_SOURCE = "MR_MONITOR"
CORRECT_EVENT_IDS = [68, 112, 282, 401, 61, 101, 102, 150, 250, 251, 248, 114]
INCORRECT_SOURCE = "WRONG_SRC"
INCORRECT_EVENT_IDS = [4, 8, 15, 16, 23, 42]


def _test_storage_event_notification(distrib_url, one_vm_type, source, event_ids, should_occur, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    assert not any(id_ in CORRECT_EVENT_IDS for id_ in INCORRECT_EVENT_IDS)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver = one_mediaserver.mediaserver()
    storage_event = EventType.STORAGE_FAILURE
    event_queue = mediaserver.api.event_queue()
    event_queue.skip_existing_events()
    mediaserver.api.disable_event_rules()

    try:
        run_powershell_script(
            WinRMShell(mediaserver.os_access.winrm),
            "New-Eventlog -LogName Application -Source $source", {"source": source})
    except PowershellError as exc:
        if "source is already registered" not in exc.message:
            raise

    mediaserver.api.add_event_rule(
        event_type=storage_event,
        event_state=EventState.UNDEFINED,
        action=RuleAction(RuleActionType.SHOW_POPUP, params={"allUsers": True}))

    for event_id in event_ids:
        # Message "Current = Failed" is important for 114 error code, for the rest message content
        # is irrelevant
        run_powershell_script(
            WinRMShell(mediaserver.os_access.winrm),
            textwrap.shorten(width=10000, text='''
                Write-EventLog
                    -LogName Application
                    -Source $source
                    -EventID $event_id
                    -EntryType Information
                    -Message "Current = Failed"
                    -Category 1
                '''),
            {"source": source, "event_id": event_id})

        try:
            event = event_queue.wait_for_next(timeout_sec=5)
            assert event.event_type == storage_event
        except EventNotOccurred:
            event = None

        assert bool(event) == should_occur, (
            "Event did{} occur for source {} and event id {}."
            .format(" not" if should_occur else "", source, event_id))
