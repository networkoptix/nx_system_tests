# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
class ExplicitMergeError(Exception):

    def __init__(self, local, remote_url, error_code, error_string):
        super(ExplicitMergeError, self).__init__(
            f"Request {local} to merge with {remote_url}: {error_code:d} {error_string}")
        self.error_string = error_string


class CloudSystemsHaveDifferentOwners(ExplicitMergeError):
    pass


class DependentSystemBoundToCloud(ExplicitMergeError):
    pass


class IncompatibleCloud(ExplicitMergeError):
    pass


class MergeDuplicateMediaserverFound(ExplicitMergeError):
    pass
