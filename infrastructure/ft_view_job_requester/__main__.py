# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from config import global_config
from infrastructure._logging import init_logging
from infrastructure._message_broker_config import get_service_client
from infrastructure._task import TaskIngress
from infrastructure._uri import get_process_uri
from infrastructure.ft_view_job_requester._job_to_task import FTViewJobInput


def main():
    message_broker = get_service_client()
    ingresses = [
        TaskIngress(
            FTViewJobInput(
                machinery=global_config['ft_machinery_url'],
                fetch_uri=global_config['ft_fetch_uri'],
                ),
            message_broker.get_producer('ft:tasks_batch_run'),
            message_broker.get_producer('ft:ft_view_job_updates'),
            ),
        ]
    while True:
        for ingress in ingresses:
            ingress.process_one_task()
            time.sleep(0.01)


if __name__ == '__main__':
    init_logging(get_process_uri())
    main()
