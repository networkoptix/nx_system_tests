# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import shlex

from provisioning._core import Run


class CommentLine(Run):

    def __init__(self, path, pattern):
        pattern = pattern.replace('/', '\\/')
        super().__init__(' '.join([
            'sudo',
            'sed', '-i',
            '-e', shlex.quote('/^ *#/b'),
            '-e', shlex.quote(f'/{pattern}/ s/^/#/'),
            path,
            ]))


_logger = logging.getLogger(__name__)
