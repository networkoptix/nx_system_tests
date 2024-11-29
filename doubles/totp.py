# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import base64
import hashlib
import hmac
import struct
import time


class TimeBasedOtp:
    DIGITS = 6

    def __init__(self, secret_key: str) -> None:
        self._secret = base64.b32decode(secret_key, True)

    def generate_otp(self) -> str:
        at_time = time.time()
        current_time = int(at_time) // 30
        hashsum = hmac.new(self._secret, struct.pack('>Q', current_time), hashlib.sha1).digest()
        offset = hashsum[-1] & 0x0F
        code = struct.unpack('>I', hashsum[offset:offset + 4])[0] & 0x7FFFFFFF
        return str(code).zfill(self.DIGITS)[-self.DIGITS:]
