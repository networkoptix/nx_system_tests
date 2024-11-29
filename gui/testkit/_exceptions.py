# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
class TestKitConnectionError(Exception):
    pass


class ObjectNotFound(Exception):
    pass


class ObjectAttributeNotFound(Exception):
    pass


class ObjectAttributeValueError(Exception):
    pass


class MouseModifierValueError(Exception):
    pass


class TypedTextValueError(Exception):
    pass
