# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import itertools
import json
import logging
import re
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from pathlib import Path
from typing import Any
from typing import Mapping
from urllib.request import Request
from urllib.request import urlopen

from infrastructure.gitlab_job_watcher._notification_channel import GitLabJobNotification
from infrastructure.gitlab_job_watcher._notification_channel import GitLabNotificationChannel


class FTPipelineFailures(GitLabNotificationChannel):

    def __init__(self):
        token_path = Path('~/.config/.secrets/slack_gitlab_failures_token.txt').expanduser()
        self._token = token_path.read_text().strip()
        self._channel_id = 'C07RGD24P0S'
        self._app_id = 'A07RGD45L02'

    def list_recent_notifications(self):
        show_after = datetime.now(tz=timezone.utc) - timedelta(days=21)
        batch_size = 500
        message_limit = 1500
        messages_fetched = 0
        cursor = ''
        result = []
        while True:
            response_data = self._request('https://slack.com/api/conversations.history', 'POST', data={
                'channel': self._channel_id,
                'limit': batch_size,
                'oldest': str(show_after.timestamp()),
                'cursor': cursor,
                })
            for message in response_data['messages']:
                if message.get('app_id') != self._app_id:
                    _logger.debug("Not our message: %s", message)
                    continue
                message_blocks = message['blocks']
                if not all(b['type'] == 'section' for b in message_blocks):
                    _logger.debug("Not a GitLab failure notification: %s", message)
                    continue
                for section in message_blocks:
                    try:
                        notification = _PostedNotification(section.get('text', {}).get('text', ''))
                    except _NotificationParsingFailed as e:
                        _logger.debug("Section %s: error %s", section, e)
                    else:
                        result.append(notification)
            cursor = response_data.get('response_metadata', {}).get('next_cursor', '')
            if not cursor:
                break
            messages_fetched += len(response_data['messages'])
            if messages_fetched >= message_limit:
                break
        return result

    def notify(self, notifications):
        blocks_per_request = 40
        for i in range(0, len(notifications), blocks_per_request):
            self._request('https://slack.com/api/chat.postMessage', 'POST', data={
                'channel': self._channel_id,
                'blocks': [{
                    'type': 'section',
                    'text': {
                        'type': 'mrkdwn',
                        'text': notification.serialize(),
                        },
                    }
                    for notification in itertools.islice(notifications, i, i + blocks_per_request)
                    ],
                })

    def _request(self, url: str, method: str, data: Mapping[str, str]) -> Mapping[str, Any]:
        _logger.debug("Request %s %s: %s", method, url, data)
        data = json.dumps(data).encode('utf-8')
        request = Request(url, method=method, data=data, headers={
            'Content-Type': 'application/json; charset=utf-8',
            'Content-Length': str(len(data)),
            'Authorization': f'Bearer {self._token}'})
        with urlopen(request, timeout=30) as response:
            response_data = response.read()
            _logger.debug("Response: %s", response_data)
            response = json.loads(response_data)
            if not response.get('ok', False):
                raise RuntimeError(
                    f"Request failed: error={response.get('error', '')!r}, "
                    f"errors={response.get('errors', [])!r}")
            return response


class _PostedNotification(GitLabJobNotification):
    _job_url_re = re.compile(r'https://gitlab.nxvms.dev/[a-zA-Z\d/_-]+/-/jobs/\d+')

    def __init__(self, message: str):
        match = self._job_url_re.search(message)
        if match is None:
            raise _NotificationParsingFailed(f"Failed to get job URL: {message}")
        self._message = message
        self._job_url = match.group()

    def job_url(self):
        return self._job_url

    def serialize(self):
        return self._message


class _NotificationParsingFailed(Exception):
    pass


_logger = logging.getLogger(__name__)
