# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
class NodeNotFoundError(Exception):

    def __init__(self, node, target='resource tree'):
        self._node = node
        self._target = target

    def __str__(self):
        return f"{self._node} node is not present in {self._target}"
