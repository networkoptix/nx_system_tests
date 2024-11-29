# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from collections import namedtuple

Run = namedtuple('Run', ['server', 'expected_cameras'])


class ServerConfig:

    def __init__(
            self,
            transactions_limit_before,
            transactions_limit_after,
            name='VMS_mediaserver',
            ):
        self.transactions_limit_before = transactions_limit_before
        self.offline_statuses_limit_before = 0
        self.transactions_limit_after = transactions_limit_after
        self.offline_statuses_limit_after = None
        self.name = name

    def set_offline_statuses_limit_after(self, cameras_count: int):
        self.offline_statuses_limit_after = 5 * cameras_count
