# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import argparse
import logging
import sys
from typing import Sequence

from infrastructure.message_broker._redis_admin import DeleteStream
from infrastructure.message_broker._redis_admin import run_with_confirmation


def main(args: Sequence[str]) -> int:
    parsed_args = _parse_args(args)
    run_with_confirmation(DeleteStream(parsed_args.stream))
    return 0


def _parse_args(args: Sequence[str]):
    parser = argparse.ArgumentParser()
    parser.add_argument('stream', metavar='STREAM', help='Stream name')
    return parser.parse_args(args)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    exit(main(sys.argv[1:]))
