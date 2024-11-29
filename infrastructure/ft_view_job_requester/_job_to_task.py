# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from datetime import datetime

from infrastructure._task import TaskInput
from infrastructure.ft_view import _db
from infrastructure.ft_view_job_requester._task import ft_task_db_to_redis

_logger = logging.getLogger(__name__)


class FTViewJobInput(TaskInput):

    def __init__(self, machinery: str, fetch_uri: str):
        self._machinery = machinery
        self._fetch_uri = fetch_uri

    def __repr__(self):
        return (
            f'{self.__class__.__name__}('
            f'machinery={self._machinery}, '
            f'fetch_uri={self._fetch_uri})'
            )

    def request_new_task(self):
        taken_at = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
        rows = _db.write_returning(
            'SELECT * FROM pop_job(%(machinery)s, %(prefix)s, %(new_status)s);', {
                'machinery': self._machinery,
                'prefix': 'queued',
                'new_status': f'taken_{taken_at}',
                })
        if not rows:
            return None
        [row] = rows
        return ft_task_db_to_redis({**row, 'job_run_id': taken_at}, self._fetch_uri)
