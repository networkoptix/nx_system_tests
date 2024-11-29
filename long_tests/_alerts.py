# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import logging
from abc import ABCMeta
from abc import abstractmethod
from collections.abc import Collection
from collections.abc import Iterable
from collections.abc import Mapping
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import requests

from _internal.service_registry import elasticsearch


class Alert:

    def __init__(self, alert_type: str, created: datetime, message: str, version: str):
        self.type = alert_type
        self._created = created
        self._message = message
        self._version = version

    @classmethod
    def from_dict(cls, fields: Mapping[str, Any]) -> 'Alert':
        if isinstance(fields['created'], str):
            created_timestamp = datetime.fromisoformat(fields['created'])
        else:
            created_timestamp = fields['created']
        return cls(
            alert_type=fields['type'],
            created=created_timestamp,
            message=fields['message'],
            version=fields['version'],
            )

    def as_dict(self) -> Mapping[str, Any]:
        return {
            'type': self.type,
            'created': self._created.isoformat(timespec='microseconds'),
            'message': self._message,
            'version': self._version,
            }

    def as_text(self) -> str:
        return '\n'.join([
            f'type: {self.type}',
            f'version: {self._version}',
            f'message: {self._message}',
            f'created: {self._created.isoformat(timespec="microseconds")}',
            ])

    def __hash__(self):
        return hash((self.type, self._version))

    def __eq__(self, other: 'Alert') -> bool:
        return self.type == other.type and self._version == other._version


class AlertsService:

    def __init__(self):
        self._storage = _AlertsStorage(elasticsearch)

    def produce_alerts(self, subject: str, alerts: Collection[Alert], transport: '_AlertsTransport'):
        existing_alerts = self._storage.load_alerts({alert.type for alert in alerts})
        new_alerts = set(alerts) - set(existing_alerts)
        if new_alerts:
            _logger.info(f"New alerts were found: {len(new_alerts)}")
            self._storage.save_alerts(new_alerts)
            transport.send(subject, new_alerts)
        else:
            _logger.info("There are no new alerts")


class _AlertsTransport(metaclass=ABCMeta):

    @abstractmethod
    def send(self, subject: str, alerts: Collection[Alert]):
        pass


class MailgunTransport(_AlertsTransport):
    """Send alerts via email through the Mailgun service.

    It uses a free tier plan.
    """

    # See: https://www.mailgun.com
    _RECIPIENTS = ('vkuzmin@networkoptix.com',)
    _DOMAIN = 'sandbox356b548aa8c9492a8d329fb9245b63c6.mailgun.org'

    def send(self, subject: str, alerts: Collection[Alert]):
        parameters = {
            'from': 'alert@networkoptix.com',
            'to': self._RECIPIENTS,
            'subject': subject,
            'text': '\n\n'.join([a.as_text() for a in alerts]),
            }
        response = requests.post(
            url=f'https://api.mailgun.net/v3/{self._DOMAIN}/messages',
            auth=self._make_auth_key(),
            data=parameters,
            )
        if 200 <= response.status_code < 300:
            _logger.info("Alerts were sent: %d", len(alerts))
        else:
            raise MailgunTransportError(f"HTTP {response.status_code}: {response.text}")

    @lru_cache
    def _make_auth_key(self) -> tuple[str, str]:
        token_path = Path('~/.config/.secrets/mailgun_token').expanduser()
        token = token_path.read_text(encoding='ascii').strip('\n ')
        return 'api', token


class _AlertsStorage:

    def __init__(self, elastic_client):
        self._elastic_client = elastic_client

    def load_alerts(self, types: Collection[str]) -> Collection[Alert]:
        _query_get_alerts = {
            "size": 10000,
            "query": {
                "bool": {
                    "filter": [
                        {
                            "terms": {
                                "type": list(types),
                                },
                            },
                        ],
                    },
                },
            }
        result = self._elastic_client.search('ft-alerts-*', json.dumps(_query_get_alerts))
        alerts = [Alert.from_dict(data['_source']) for data in result['hits']['hits']]
        return alerts

    def save_alerts(self, alerts: Iterable[Alert]):
        for one_alert in alerts:
            self._elastic_client.send('ft-alerts-{YYYY}', one_alert.as_dict())
        elasticsearch.flush()


class AlertsServiceError(Exception):
    pass


class ElasticsearchError(AlertsServiceError):
    pass


class MailgunTransportError(AlertsServiceError):
    pass


_logger = logging.getLogger(__name__)
