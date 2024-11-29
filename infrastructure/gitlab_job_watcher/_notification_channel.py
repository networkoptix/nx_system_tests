# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from abc import ABCMeta
from abc import abstractmethod
from typing import Collection
from typing import Sequence
from typing import TypeVar

from infrastructure.gitlab import PipelineJob


class GitLabNotificationChannel(metaclass=ABCMeta):

    @abstractmethod
    def list_recent_notifications(self) -> Sequence['GitLabJobNotification']:
        pass

    @abstractmethod
    def notify(self, notifications: Collection['GitLabJobNotification']):
        pass


_GitLabJobNotificationT = TypeVar('_GitLabJobNotificationT', bound='GitLabJobNotification')


class _NotificationFilter(metaclass=ABCMeta):

    @abstractmethod
    def apply(
            self,
            notifications: Collection['_GitLabJobNotificationT'],
            ) -> Collection['_GitLabJobNotificationT']:
        pass


class NewNotifications(_NotificationFilter):

    def __init__(self, channel: GitLabNotificationChannel):
        self._channel = channel

    def apply(self, notifications):
        posted_jobs = [n.job_url() for n in self._channel.list_recent_notifications()]
        result = []
        for notification in notifications:
            if notification.job_url() not in posted_jobs:
                result.append(notification)
            else:
                _logger.debug("Already reported: %r", notification)
        return result


class GitLabJobNotification(metaclass=ABCMeta):

    @abstractmethod
    def job_url(self) -> str:
        pass

    @abstractmethod
    def serialize(self) -> str:
        pass


class MarkdownNotification(GitLabJobNotification):
    _template = '`{project_name}` / <{pipeline_url}|{pipeline_url_short}> / <{job_url}|{job_url_short}>'

    def __init__(self, project_name: str, job: PipelineJob):
        self._project_name = project_name
        self._pipeline_url = job.pipeline_url()
        [*_, self._pipeline_url_short] = self._pipeline_url.split('/-/', 1)
        self._job_name = job.name()
        self._job_url = job.url()

    def __repr__(self):
        return f"<{self.__class__.__name__} {self._job_url}>"

    def job_url(self):
        return self._job_url

    def serialize(self) -> str:
        return self._template.format(
            project_name=self._project_name,
            pipeline_url=self._pipeline_url,
            pipeline_url_short=self._pipeline_url_short,
            job_url=self._job_url,
            job_url_short=self._job_name,
            )


_logger = logging.getLogger(__name__)
