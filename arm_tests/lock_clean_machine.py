# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from argparse import ArgumentParser
from contextlib import closing

from arm_tests.arm_manager_client import HighPriorityMarket
from arm_tests.machine_description import get_machine_description
from arm_tests.machines_market import MachineDescription
from arm_tests.machines_market import RootSnapshot


def _lock_clean_machine(machine_description: MachineDescription):
    with RootSnapshot(machine_description).lease(HighPriorityMarket()) as running_machine:
        with closing(running_machine.get_os_access()) as os_access:
            ssh_username = os_access.user()
            netloc = os_access.netloc()
            machine_access_url = f"ssh://{ssh_username}@{netloc}"
            os_access.wait_ready(timeout_sec=90)
            _logger.warning("%s is online", machine_access_url)
        logging.warning(
            "Now you have exclusive access to a clean %s at %s for 24 hours.",
            running_machine, machine_access_url,
            )
        logging.warning("All data will be automatically wiped when this script exits")
        try:
            running_machine.monitor(timeout=24 * 60 * 60)
        except KeyboardInterrupt:
            _logger.info("%s is released manually", running_machine)
        else:
            _logger.info("24 hours have passed. Lock of %s has expired", running_machine)


_logger = logging.getLogger(__name__)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)7s %(name)s %(message).5000s")
    parser = ArgumentParser(description='ARM board locking script')
    parser.add_argument(
        '--model',
        dest='model',
        required=True,
        help='ARM machine model to install mediaserver on',
        )
    parser.add_argument(
        '--arch',
        dest='arch',
        help='ARM architecture',
        )
    parser.add_argument(
        '--os',
        dest='os',
        help='ARM Operation System',
        )
    parser.add_argument(
        '--name',
        dest='name',
        required=False,
        help='ARM board Operation System',
        )
    _lock_clean_machine(get_machine_description(parser.parse_args()))
