# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import argparse
import sys
import time
from typing import Sequence

from infrastructure._logging import init_logging
from infrastructure._message_broker_config import get_default_client
from infrastructure._uri import get_group_uri
from infrastructure._uri import get_process_uri
from infrastructure.worker._worker import Worker


def main(args: Sequence[str]):
    parsed_args = _parse_args(args)
    worker_uri = get_process_uri()
    started_at = time.monotonic()
    try:
        _run_single_task(worker_uri, parsed_args.input_stream, parsed_args.output_stream)
    finally:
        # Limit worker restart rate. When queue is empty - workers are restarting too fast
        # and are reaching systemd internal restart limits.
        time.sleep(max(0., started_at + 10 - time.monotonic()))


def _run_single_task(worker_uri: str, input_stream: str, output_stream: str):
    message_broker = get_default_client()
    worker = Worker(
        worker_uri,
        message_broker.get_consumer(input_stream, get_group_uri(), worker_uri),
        message_broker.get_producer(output_stream),
        message_broker.get_producer('ft:worker_state_updates'),
        )
    worker.run_single_task()


def _parse_args(args: Sequence[str]):
    parser = argparse.ArgumentParser()
    parser.add_argument('input_stream', help="Stream name to consume tasks from.")
    parser.add_argument('output_stream', help="Stream name to report task updates to.")
    return parser.parse_args(args)


if __name__ == '__main__':
    init_logging(get_process_uri())
    main(sys.argv[1:])
