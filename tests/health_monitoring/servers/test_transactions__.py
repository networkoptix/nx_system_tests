# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from functools import partial

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import ApproxAbs
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.waiting import wait_for_truthy


def _test_transactions(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver_api = one_mediaserver.mediaserver().api
    server_id = mediaserver_api.get_server_id()
    wait_for_truthy(
        lambda: mediaserver_api.get_metrics('servers', server_id, 'transactions_per_sec') > 0,
        description="Initial transactions detected")
    metrics_period_sec = 60
    wait_for_transactions = partial(
        mediaserver_api.wait_for_metric, 'servers', server_id, 'transactions_per_sec')
    wait_for_transactions(expected=0, timeout_sec=metrics_period_sec + 10)
    for transaction_number in range(1, 11):
        mediaserver_api.rename_server(f"new_name_{transaction_number}", server_id)
        wait_for_transactions(
            expected=ApproxAbs(transaction_number / metrics_period_sec, 1e-5),
            timeout_sec=10)
    wait_for_transactions(expected=0, timeout_sec=metrics_period_sec + 10)
