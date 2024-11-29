# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

started_at = time.monotonic()
while True:
    print("message to stdout", flush=True)
    time.sleep(0.2)
    if time.monotonic() - started_at > 60:
        break
