# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import sys
import time
from contextlib import ExitStack
from datetime import datetime
from datetime import timedelta
from ipaddress import IPv4Network
from itertools import chain
from typing import Collection

from browser.chrome.provisioned_chrome import chrome_stand
from browser.webdriver import Browser
from directories import get_run_dir
from distrib import Distrib
from doubles.licensing.local_license_server import LocalLicenseServer
from installation import ClassicInstallerSupplier
from installation import upload_web_admin_to_mediaserver
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from runner.ft_test import run_ft_test
from tests.base_test import WebAdminTest
from tests.web_admin._collect_version import collect_version
from tests.web_admin._licenses import ActiveKey
from tests.web_admin._licenses import Channels
from tests.web_admin._licenses import LicensesForm
from tests.web_admin._licenses import get_active_keys_by_rows
from tests.web_admin._licenses import get_active_keys_names_first
from tests.web_admin._login import LoginForm
from tests.web_admin._main_menu import MainMenu
from vm.networks import setup_flat_network


class test_activate_multiple_license(WebAdminTest):
    """Test activate multiple license.

    Selection-Tag: web-admin-gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/84068
    """

    def _run(self, args, exit_stack: ExitStack):
        _test(args, exit_stack)


def _test(args, exit_stack: ExitStack):
    one_vm_type = 'ubuntu22'
    installer_supplier = ClassicInstallerSupplier(args.distrib_url)
    distrib = installer_supplier.distrib()
    pool = FTMachinePool(installer_supplier, get_run_dir(), 'v2')
    first_stand = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    second_stand = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    browser_stand = exit_stack.enter_context(chrome_stand([]))
    [[first_mediaserver_ip, second_mediaserver_ip, _], _] = setup_flat_network(
        [first_stand.vm(), second_stand.vm(), browser_stand.vm()],
        IPv4Network('10.254.10.0/28'),
        )
    first_api = first_stand.api()
    first_mediaserver = first_stand.mediaserver()
    second_api = second_stand.api()
    second_mediaserver = second_stand.mediaserver()
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    first_mediaserver.start()
    second_mediaserver.start()
    upload_web_admin_to_mediaserver(first_api, args.webadmin_url)
    license_server_url = license_server.url()
    first_api.setup_local_system({'licenseServer': license_server_url})
    second_api.setup_local_system({'licenseServer': license_server_url})
    first_server_name = "first"
    second_server_name = "second"
    first_api.rename_server(first_server_name)
    second_api.rename_server(second_server_name)
    merge_systems(first_mediaserver, second_mediaserver, take_remote_settings=False)
    expected_keys = set()
    brand = first_api.get_brand()
    permanent_professional_key = license_server.generate(
        {'QUANTITY2': 4, 'CLASS2': 'digital', 'BRAND2': brand})
    expected_keys.add(ActiveKey(permanent_professional_key, 4, None))
    today = datetime.now().date()
    temporary_professional_key_expiration_date = today + timedelta(days=31)
    temporary_professional_key = license_server.generate({
        'QUANTITY2': 4,
        'CLASS2': 'digital',
        'BRAND2': brand,
        'FIXED_EXPIRATION_TS': temporary_professional_key_expiration_date.strftime('%m/%d/%Y'),
        })
    expected_keys.add(
        ActiveKey(temporary_professional_key, 4, temporary_professional_key_expiration_date))
    temporary_analog_key_expiration_date = today + timedelta(days=32)
    temporary_analog_key = license_server.generate({
        'QUANTITY2': 5,
        'CLASS2': 'analog',
        'BRAND2': brand,
        'FIXED_EXPIRATION_TS': temporary_analog_key_expiration_date.strftime('%m/%d/%Y'),
        })
    expected_keys.add(
        ActiveKey(temporary_analog_key, 5, temporary_analog_key_expiration_date))
    temporary_vmax_key_expiration_date = today + timedelta(days=33)
    temporary_vmax_key = license_server.generate({
        'QUANTITY2': 6,
        'CLASS2': 'vmax',
        'BRAND2': brand,
        'FIXED_EXPIRATION_TS': temporary_vmax_key_expiration_date.strftime('%m/%d/%Y'),
        })
    expected_keys.add(
        ActiveKey(temporary_vmax_key, 6, temporary_vmax_key_expiration_date))
    temporary_analog_encoder_key_expiration_date = today + timedelta(days=34)
    temporary_analog_encoder_key = license_server.generate({
        'QUANTITY2': 7,
        'CLASS2': 'analogencoder',
        'BRAND2': brand,
        'FIXED_EXPIRATION_TS': temporary_analog_encoder_key_expiration_date.strftime('%m/%d/%Y'),
        })
    expected_keys.add(
        ActiveKey(temporary_analog_encoder_key, 7, temporary_analog_encoder_key_expiration_date))
    temporary_edge_key_expiration_date = today + timedelta(days=35)
    temporary_edge_key = license_server.generate({
        'QUANTITY2': 8,
        'CLASS2': 'edge',
        'BRAND2': brand,
        'FIXED_EXPIRATION_TS': temporary_edge_key_expiration_date.strftime('%m/%d/%Y'),
        })
    expected_keys.add(ActiveKey(temporary_edge_key, 8, temporary_edge_key_expiration_date))
    temporary_iomodule_key_expiration_date = today + timedelta(days=36)
    temporary_iomodule_key = license_server.generate({
        'QUANTITY2': 9,
        'CLASS2': 'iomodule',
        'BRAND2': brand,
        'FIXED_EXPIRATION_TS': temporary_iomodule_key_expiration_date.strftime('%m/%d/%Y'),
        })
    expected_keys.add(
        ActiveKey(temporary_iomodule_key, 9, temporary_iomodule_key_expiration_date))
    temporary_bridge_key_expiration_date = today + timedelta(days=37)
    temporary_bridge_key = license_server.generate({
        'QUANTITY2': 10,
        'CLASS2': 'bridge',
        'BRAND2': brand,
        'FIXED_EXPIRATION_TS': temporary_bridge_key_expiration_date.strftime('%m/%d/%Y'),
        })
    expected_keys.add(ActiveKey(temporary_bridge_key, 10, temporary_bridge_key_expiration_date))
    browser = exit_stack.enter_context(browser_stand.browser())
    collect_version(browser, first_mediaserver.url(first_mediaserver_ip))
    browser.open(first_mediaserver.url(first_mediaserver_ip))
    first_local_administrator_credentials = first_api.get_credentials()
    login_form = LoginForm(browser)
    login_form.get_login_field().put(first_local_administrator_credentials.username)
    login_form.get_password_field().put(first_local_administrator_credentials.password)
    login_form.get_submit_button().invoke()
    _activate_license(browser, first_server_name, permanent_professional_key)
    _activate_license(browser, second_server_name, temporary_professional_key)
    _activate_license(browser, second_server_name, temporary_analog_key)
    _activate_license(browser, second_server_name, temporary_vmax_key)
    _activate_license(browser, second_server_name, temporary_analog_encoder_key)
    _activate_license(browser, second_server_name, temporary_edge_key)
    _activate_license(browser, second_server_name, temporary_iomodule_key)
    _activate_license(browser, second_server_name, temporary_bridge_key)
    first_channels_summary = _get_channels_summary(browser)
    first_server_active_keys = _get_active_keys(browser, distrib, persistent_sec=5)
    [one, another] = first_server_active_keys.keys()
    assert one.id != another.id
    assert {one.name, another.name} == {first_server_name, second_server_name}
    assert expected_keys == set(chain(*first_server_active_keys.values()))
    browser.open(first_mediaserver.url(second_mediaserver_ip))
    second_local_administrator_credentials = second_api.get_credentials()
    login_form = LoginForm(browser)
    login_form.get_login_field().put(second_local_administrator_credentials.username)
    login_form.get_password_field().put(second_local_administrator_credentials.password)
    login_form.get_submit_button().invoke()
    MainMenu(browser).get_licenses_link().invoke()
    second_channels_summary = _get_channels_summary(browser)
    assert len(first_channels_summary) == len(second_channels_summary) == 2
    second_server_active_keys = _get_active_keys(browser, distrib, persistent_sec=5)
    [one, another] = second_server_active_keys.keys()
    assert one.id != another.id
    assert {one.name, another.name} == {first_server_name, second_server_name}
    assert expected_keys == set(chain(*second_server_active_keys.values()))


def _activate_license(browser: Browser, server_name: str, key: str):
    main_menu = MainMenu(browser)
    main_menu.get_licenses_link().invoke()
    licenses_form = LicensesForm(browser)
    licenses_form.choose_server(server_name)
    licenses_form.get_license_input().put(key)
    licenses_form.get_activate_button().invoke()


def _get_channels_summary(browser: Browser) -> Collection[Channels]:
    main_menu = MainMenu(browser)
    main_menu.get_licenses_link().invoke()
    browser.refresh()
    return LicensesForm(browser).get_channels_summary().values()


def _get_active_keys(browser: Browser, distrib: Distrib, persistent_sec: float):
    # Keys blocks are displayed a little bit after the nx-license-detail-component is displayed
    # what leads to an incomplete output.
    defensive_timeout_at = time.monotonic() + 60
    result = {}
    last_changed = time.monotonic()
    while True:
        now = time.monotonic()
        if distrib.newer_than('vms_6.0'):
            # TODO: Remove try/except clause after WebAdmin version is bumped after the MR
            #  mentioned below and disappearance of 6.1 builds containing older WebAdmin versions.
            #  The exact removal date is unpredictable due to asynchronous nature of WebAdmin updates.
            try:
                current_result = get_active_keys_by_rows(browser)
            except ValueError as err:
                if 'invalid literal for int() with base 10' in str(err):
                    _logger.warning(
                        "Observed obsoleted behavior on VMS 6.1 due to "
                        "https://gitlab.nxvms.dev/dev/cloud_portal/-/merge_requests/8566")
                    current_result = get_active_keys_names_first(browser)
                else:
                    raise
        else:
            current_result = get_active_keys_names_first(browser)
        if current_result == result:
            if last_changed + persistent_sec < now:
                return current_result
        else:
            result = current_result
            last_changed = now
        if now > defensive_timeout_at:
            raise RuntimeError(
                f"Result persistence is not achieved after {defensive_timeout_at} seconds")
        time.sleep(0.2)


_logger = logging.getLogger(__file__)


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_activate_multiple_license()]))
