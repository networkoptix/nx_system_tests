# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import base64
import hashlib


def user_digest(realm, username, password):
    data = ':'.join([username.lower(), realm, password])
    data = data.encode()
    data = hashlib.md5(data)
    data = data.hexdigest()
    return data


def calculate_digest(method: str, path: str, realm: str, nonce: str, user: str, password: str) -> str:
    ha1 = user_digest(realm, user, password)
    ha2 = hashlib.md5(':'.join([method, path]).encode()).hexdigest()  # Empty path.
    result = hashlib.md5(':'.join([ha1, nonce, ha2]).encode()).hexdigest()
    return result


def key(method, path, realm, nonce, user, password):
    # `requests.auth.HTTPDigestAuth.build_digest_header` does the same but it substitutes empty path with '/'.
    # No straightforward way of getting key has been found.
    # This method is used only for specific tests, so there is no need to save one HTTP request.
    digest_ = calculate_digest(method=method, path=path, realm=realm, nonce=nonce, user=user, password=password)
    result = base64.b64encode(':'.join([user.lower(), nonce, digest_]).encode())
    return result.decode('ascii')
