# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from functools import lru_cache

from config import global_config
from infrastructure._logging import init_logging
from infrastructure._message_broker_config import get_service_client
from infrastructure._task import TaskIngress
from infrastructure._uri import get_process_uri
from infrastructure.gitlab_job_requester._job_to_task import GitlabJobInput
from infrastructure.gitlab_job_requester._runner import GitlabRunner


def main():
    ingresses = [
        _gitlab_task_ingress(
            '~/.config/.secrets/runner_token_fast.txt',
            'ft:tasks_fast',
            global_config['ft_fetch_uri'],
            ),
        _gitlab_task_ingress(
            '~/.config/.secrets/runner_token_batches_ft.txt',
            'ft:tasks_batch_poll',
            global_config['ft_fetch_uri'],
            ),
        _gitlab_task_ingress(
            '~/.config/.secrets/runner_token_batches_gui.txt',
            'ft:tasks_batch_poll',
            global_config['ft_fetch_uri'],
            ),
        _gitlab_task_ingress(
            '~/.config/.secrets/runner_token_ft_installation.txt',
            'ft:tasks_snapshot_vbox',
            global_config['ft_fetch_uri'],
            ),
        _gitlab_task_ingress(
            '~/.config/.secrets/runner_token_snapshots_jetsonnano.txt',
            'ft:tasks_snapshot_jetsonnano',
            global_config['ft_fetch_uri'],
            ),
        _gitlab_task_ingress(
            '~/.config/.secrets/runner_token_snapshots_orinnano.txt',
            'ft:tasks_snapshot_orinnano',
            global_config['ft_fetch_uri'],
            ),
        _gitlab_task_ingress(
            '~/.config/.secrets/runner_token_snapshots_rpi4.txt',
            'ft:tasks_snapshot_rpi4',
            global_config['ft_fetch_uri'],
            ),
        _gitlab_task_ingress(
            '~/.config/.secrets/runner_token_snapshots_rpi5.txt',
            'ft:tasks_snapshot_rpi5',
            global_config['ft_fetch_uri'],
            ),
        _gitlab_task_ingress(
            '~/.config/.secrets/runner_token_cloud_portal_tests.txt',
            'ft:tasks_batch_poll',
            global_config['ft_fetch_uri'],
            ),
        ]
    while True:
        for ingress in ingresses:
            ingress.process_one_task()
            time.sleep(0.01)


def _gitlab_task_ingress(token_path: str, output: str, repo_uri: str) -> TaskIngress:
    return TaskIngress(
        GitlabJobInput(
            GitlabRunner('https://gitlab.nxvms.dev/', token_path),
            repo_uri,
            ),
        _message_broker().get_producer(output),
        _message_broker().get_producer('ft:gitlab_job_updates'),
        )


@lru_cache(1)
def _message_broker():
    return get_service_client()


if __name__ == '__main__':
    init_logging(get_process_uri())
    main()
