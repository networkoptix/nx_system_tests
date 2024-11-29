# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from argparse import ArgumentParser

from arm_tests.arm_manager_client import MiddlePriorityMarket
from arm_tests.machine_description import get_machine_description
from arm_tests.machines_market import ClientPrerequisitesSnapshot

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s %(levelname)7s %(name)s %(message).5000s")
    parser = ArgumentParser(description='Prerequisites builder')
    parser.add_argument(
        '--model',
        dest='model',
        required=True,
        help='ARM machine model',
        )
    parser.add_argument(
        '--arch',
        dest='arch',
        required=True,
        help='ARM architecture',
        )
    parser.add_argument(
        '--os',
        dest='os',
        required=True,
        help='ARM Operation System',
        )
    machine_description = get_machine_description(parser.parse_args())
    ClientPrerequisitesSnapshot(machine_description).prepare(MiddlePriorityMarket())
