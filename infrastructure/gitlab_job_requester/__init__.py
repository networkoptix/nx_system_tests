# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from infrastructure.gitlab_job_requester._job_to_task import GitlabJobInput
from infrastructure.gitlab_job_requester._runner import GitlabRunner

__all__ = [
    'GitlabJobInput',
    'GitlabRunner',
    ]
