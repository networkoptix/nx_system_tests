# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys
import textwrap
from functools import partial

from cloud_api.cloud import make_cloud_account_factory
from cloud_api.cloud import make_push_notification_viewer
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import EventState
from mediaserver_api import EventType
from mediaserver_api import RuleAction
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from os_access._powershell import PowershellError
from os_access._powershell import run_powershell_script
from os_access._winrm_shell import WinRMShell
from runner.ft_test import run_ft_test
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud.push_notifications.conftest import configure_for_push_notifications

storage_issue_titles_old = {
    'ru_RU': '\N{CROSS MARK} Ошибка хранилища',
    'ko_KR': '\N{CROSS MARK} 저장공간 문제',
    'ja_JP': '\N{CROSS MARK} ストレージ障害',
    'zh_CN': '\N{CROSS MARK} 存储问题',
    'th_TH': '\N{CROSS MARK} พื้นที่จัดเก็บมีปัญหา',
    'he_IL': '\N{CROSS MARK} בעיית אחסון',
    'tr_TR': '\N{CROSS MARK} Depolama sorunu',
    'es_ES': '\N{CROSS MARK} Problema con el almacenamiento',
    'de_DE': '\N{CROSS MARK} Speicherproblem',
    'pt_PT': '\N{CROSS MARK} Problema de armazenamento',
    }

storage_issue_titles_new = {
    'ru_RU': '\N{CROSS MARK} Ошибка хранилища',
    'ko_KR': '\N{CROSS MARK} 저장공간 문제',
    'ja_JP': '\N{CROSS MARK} ストレージエラー',
    'zh_CN': '\N{CROSS MARK} 存储问题',
    'th_TH': '\N{CROSS MARK} พื้นที่จัดเก็บมีปัญหา',
    'he_IL': '\N{CROSS MARK} בעיית אחסון',
    'tr_TR': '\N{CROSS MARK} Depolama sorunu',
    'es_ES': '\N{CROSS MARK} Problema con el almacenamiento',
    'de_DE': '\N{CROSS MARK} Speicherproblem',
    'pt_PT': '\N{CROSS MARK} Problema de armazenamento',
    }


class test_win11_v2(VMSTest, CloudTest):
    """Test storage failure event.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/69725
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/69726
    """

    def _run(self, args, exit_stack):
        _test_storage_failure_event(args.cloud_host, args.distrib_url, 'win11', 'v2', exit_stack)


def _test_storage_failure_event(cloud_host, distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    push_notification_viewer = make_push_notification_viewer(cloud_host)
    cloud_account_factory = make_cloud_account_factory(cloud_host)
    cloud_account = cloud_account_factory.create_account()
    customization_name = installer_supplier.distrib().customization().customization_name
    cloud_account.set_user_customization(customization_name)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    cloud_mediaserver = one_mediaserver.mediaserver()
    configure_for_push_notifications(cloud_mediaserver, cloud_host, cloud_account)
    api = cloud_mediaserver.api
    [cloud_user] = [u for u in api.list_users() if u.is_cloud]
    # After VMS-27079, there is a default storage failure notification rule, and with this rule,
    # an extra storage failure notification appears. Disable it and add another one with settings
    # more suitable for the test (the default rule has a too large aggregationPeriod).
    for rule in api.list_event_rules():
        if (rule.event, rule.action) == (EventType.STORAGE_FAILURE, 'pushNotificationAction'):
            api.disable_event_rule(rule.id)
            break
    api.add_event_rule(
        event_type=EventType.STORAGE_FAILURE,
        event_state=EventState.UNDEFINED,
        action=RuleAction.push_notification([cloud_user.id]))
    os_access = cloud_mediaserver.os_access
    # MR - MegaRaid, error code description:
    # https://www.thomas-krenn.com/de/wiki/MegaRAID_Event_Messages
    # https://www.supermicro.com/manuals/other/MegaRAID_SAS_Software_Rev_I_UG.pdf Appendix A
    try:
        run_powershell_script(
            WinRMShell(os_access.winrm),
            'New-Eventlog -LogName Application -Source $source', {'source': 'MR_MONITOR'})
    except PowershellError as exc:
        if 'source is already registered' not in exc.message:
            raise
    cloud_system_id = api.get_cloud_system_id()
    create_event_fn = partial(
        run_powershell_script,
        WinRMShell(os_access.winrm),
        textwrap.shorten(width=10000, text='''
            Write-EventLog
                -LogName Application
                -Source $source
                -EventID $event_id
                -EntryType Information
                -Message "Current = Failed"
                -Category 1
            '''),
        {'source': 'MR_MONITOR', 'event_id': 68})
    check_title_fn = partial(
        _check_notification_title, api, push_notification_viewer, cloud_system_id, create_event_fn)
    distrib = installer_supplier.distrib()
    storage_issue_titles = storage_issue_titles_new if distrib.newer_than('vms_6.0') else storage_issue_titles_old
    for language, title in storage_issue_titles.items():
        if not cloud_mediaserver.supports_language(language):
            continue
        check_title_fn(language, title)
    # Default server language
    check_title_fn('', '\N{CROSS MARK} Storage Issue')


def _check_notification_title(
        api, push_notification_viewer, cloud_system_id, create_event_fn, language, title):
    api.set_push_notification_language(language)
    with push_notification_viewer.wait_for_new_notifications(cloud_system_id):
        create_event_fn()
    [notification] = push_notification_viewer.new_notifications
    assert notification.title == title, f"Expected: {title!r}, got: {notification.title!r}"


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_win11_v2()]))
