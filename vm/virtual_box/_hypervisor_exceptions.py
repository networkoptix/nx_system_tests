# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from vm.hypervisor import HypervisorError


class VirtualBoxError(HypervisorError):
    """The base of exceptions that should not be propagate or caught outside."""

    code: str


class VirtualBoxVMNotReady(VirtualBoxError):
    pass


class VirtualBoxGuestAdditionsNotReady(VirtualBoxError):
    pass


def virtual_box_error_cls(code):
    assert code

    try:
        return virtual_box_error_cls.cache[code]
    except KeyError:
        class SpecificVirtualBoxError(VirtualBoxError):

            def __init__(self, message: str, error_text: str):
                super(SpecificVirtualBoxError, self).__init__(message)
                self.error_text = error_text

        error_cls = type('VirtualBoxError_{}'.format(code), (SpecificVirtualBoxError,), {'code': code})
        virtual_box_error_cls.cache[code] = error_cls
        return error_cls


virtual_box_error_cls.cache = {}
