# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from infrastructure._logging import init_logging
from infrastructure._message_broker_config import get_service_client
from infrastructure._task_update import UpdateService
from infrastructure._uri import get_group_uri
from infrastructure._uri import get_process_uri
from infrastructure.gitlab_job_updater._job_update import GitlabJobReportFactory


def main():
    message_broker = get_service_client()
    consumer = message_broker.get_consumer(
        'ft:gitlab_job_updates', get_group_uri(), get_process_uri())
    report_factory = GitlabJobReportFactory('https://gitlab.nxvms.dev')
    update_service = UpdateService(consumer, report_factory)
    while True:
        update_service.process_one_update()
        time.sleep(0.01)


if __name__ == '__main__':
    init_logging(get_process_uri())
    main()
