# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging.handlers
from pathlib import Path
from typing import Collection
from typing import Mapping
from typing import Sequence

from _internal.service_registry import gitlab_dev_cloud_portal
from _internal.service_registry import gitlab_dev_nx
from infrastructure.gitlab import GitlabForbidden
from infrastructure.gitlab import GitlabProject
from infrastructure.gitlab import PipelineJob
from infrastructure.gitlab_job_watcher._notification_channel import GitLabJobNotification
from infrastructure.gitlab_job_watcher._notification_channel import MarkdownNotification
from infrastructure.gitlab_job_watcher._notification_channel import NewNotifications
from infrastructure.gitlab_job_watcher._slack import FTPipelineFailures


def main():
    dev_nx_notifications = _retry_project_jobs(gitlab_dev_nx, stage_names=[
        'installation (#ask-ft)',
        'ft (#ask-ft)',
        ])
    cloud_portal_notifications = _retry_project_jobs(gitlab_dev_cloud_portal, stage_names=[
        'ft (#ask-ft)',
        ])
    notification_channel = FTPipelineFailures()
    notification_filter = NewNotifications(notification_channel)
    notification_channel.notify(notification_filter.apply([*dev_nx_notifications, *cloud_portal_notifications]))
    _logger.info("Bye")


def _retry_project_jobs(
        gitlab_project: GitlabProject,
        stage_names: Collection[str],
        ) -> Collection['GitLabJobNotification']:
    failed_pipelines = gitlab_project.list_recently_failed_pipelines()
    _logger.info("Found %d failed %s pipelines", len(failed_pipelines), gitlab_project.name())
    failure_notifications = []
    for pipeline in failed_pipelines:
        _logger.info("Check %r", pipeline)
        all_job_attempts = pipeline.list_job_attempts()
        ft_jobs = {
            job_name: attempts
            for job_name, attempts in all_job_attempts.items()
            if attempts[-1].stage() in stage_names
            }
        rest_jobs = [
            job_name
            for job_name, attempts in all_job_attempts.items()
            if attempts[-1].stage() not in stage_names
            ]
        _logger.debug(f"Not our jobs: {rest_jobs}")
        _retry_pipeline_jobs(ft_jobs, attempt_limit=2)
        failure_notifications.extend(
            MarkdownNotification(gitlab_project.name(), attempt)
            for job_attempts in ft_jobs.values()
            for attempt in job_attempts
            if attempt.status() == 'failed'
            )
    return failure_notifications


def _retry_pipeline_jobs(
        job_attempts: Mapping[str, Sequence[PipelineJob]],
        attempt_limit: int,
        ):
    for job_name, attempts in job_attempts.items():
        [*_, last_attempt] = attempts
        last_status = last_attempt.status()
        if last_status != 'failed':
            _logger.debug("Job %r: status %r, no need to retry", job_name, last_status)
            continue
        if len(attempts) >= attempt_limit:
            _logger.debug("Job %r: too many attempts, refuse to retry again", job_name)
            continue
        _logger.info("Job %r: retry", job_name)
        try:
            last_attempt.retry()
        except GitlabForbidden as e:
            _logger.info("Failed to retry job %s: %s", last_attempt, e)


_logger = logging.getLogger(__name__)


if __name__ == '__main__':
    logging.getLogger().setLevel(logging.DEBUG)
    log_file = Path('~/.cache/gitlab_job_watcher.log').expanduser()
    file_handler = logging.handlers.RotatingFileHandler(
        Path('~/.cache/gitlab_job_watcher.log').expanduser(),
        maxBytes=200 * 1024**2,
        backupCount=1)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(process)d %(threadName)s %(name)s %(levelname)s %(message)s'))
    file_handler.setLevel(logging.DEBUG)
    logging.getLogger().addHandler(file_handler)
    main()
