# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json

from infrastructure._task_update import UpdateReportFactory
from infrastructure.ft_view import _db
from infrastructure.ft_view_job_updater._update_serializarion import ft_view_update_serialize


class FTViewJobReportFactory(UpdateReportFactory):

    def send_report(self, message_raw):
        serialized = ft_view_update_serialize(message_raw)
        _db.write(
            'UPDATE job SET '
            'url = coalesce(%(task_artifacts_url)s, url), '
            'progress = coalesce(%(status)s || \'_\' || %(job_run_id)s, progress) '
            'WHERE job.cmdline = %(cmdline)s '
            ';', {
                **serialized,
                'cmdline': json.dumps(serialized['cmdline']),
                })
