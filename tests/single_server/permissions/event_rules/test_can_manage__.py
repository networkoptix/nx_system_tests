# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import EventState
from mediaserver_api import EventType
from mediaserver_api import Permissions
from mediaserver_api import RuleAction
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_can_manage(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver = one_mediaserver.mediaserver()
    event_rule_id = mediaserver.api.add_event_rule(
        event_type=EventType.USER_DEFINED,
        event_state=EventState.UNDEFINED,
        action=RuleAction('diagnosticsAction'),
        )
    test_admin_group = mediaserver.api.add_user_group('test_admin_group', [Permissions.ADMIN])
    test_admin = mediaserver.api.add_local_user(
        'test_admin', 'WellKnownPassword2', group_id=test_admin_group)
    mediaserver_api_for_actor = mediaserver.api.as_user(test_admin)
    mediaserver_api_for_actor.add_event_rule(
        event_type=EventType.USER_DEFINED,
        event_state=EventState.UNDEFINED,
        action=RuleAction('diagnosticsAction'),
        )
    mediaserver_api_for_actor.disable_event_rules()
    mediaserver_api_for_actor.remove_event_rule(event_rule_id)
    mediaserver_api_for_actor.reset_event_rules()
