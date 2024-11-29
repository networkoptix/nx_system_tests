# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import re
import time
from email import message_from_bytes
from imaplib import IMAP4_SSL
from typing import Sequence
from urllib.parse import unquote

_logger = logging.getLogger(__name__)

_ACTIVATE_YOUR_ACCOUNT_SUBJECT = 'Activate your account'


class IMAPConnection:

    def __init__(self, email: str, password: str):
        if not email:
            raise RuntimeError("Email address cannot be empty")
        if not password:
            raise RuntimeError("Password cannot be empty")
        hostname = 'imap.gmail.com'
        _logger.debug('\tIMAP: connecting to %r', hostname)
        self._connection = IMAP4_SSL(hostname)
        self._call('login', email, password)
        self._call('select')

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._call('close')

    def get_message_id_by_subject(self, email: str, subject_text: str, timeout: float = 90) -> str:
        started_at = time.monotonic()
        while True:
            message_ids = self._list_message_ids(email, subject_text)
            if message_ids:
                [newest_message_id, *_] = message_ids
                return newest_message_id
            if time.monotonic() - started_at > timeout:
                raise RuntimeError(
                    f"Timed out in {timeout} waiting for "
                    f"email with subject {subject_text} to appear")

    def get_register_link_from_message(self, message_id: str) -> str:
        response = self._call('uid', 'fetch', message_id, '(RFC822)')
        message = message_from_bytes(response[0][1])
        for part in message.walk():
            if part.get_content_type() == 'text/plain':
                payload = part.get_payload(decode=True)
                return re.search(r'https?://\S+/register/.+', payload.decode()).group(0)
        raise RuntimeError(f"Cannot get register link from message {message_id}")

    def has_link_to_cloud_instance_in_message(self, message_id: str, cloud_instance: str) -> bool:
        response = self._call('uid', 'fetch', message_id, '(RFC822)')
        message = message_from_bytes(response[0][1])
        for part in message.walk():
            if part.get_content_type() == 'text/plain':
                payload = part.get_payload(decode=True)
                if re.search(cloud_instance, payload.decode()) is not None:
                    return True
        return False

    def get_link_to_cloud_system(self, message_id: str) -> str:
        response = self._call('uid', 'fetch', message_id, '(RFC822)')
        message = message_from_bytes(response[0][1])
        for part in message.walk():
            if part.get_content_type() == 'text/plain':
                payload = part.get_payload(decode=True)
                return re.search(r'https?://\S+/systems/.+', payload.decode()).group(0)
        raise RuntimeError(f"Cannot get link to the system from message {message_id}")

    def get_restore_password_link(self, message_id: str) -> str:
        response = self._call('uid', 'fetch', message_id, '(RFC822)')
        message = message_from_bytes(response[0][1])
        for part in message.walk():
            if part.get_content_type() == 'text/plain':
                payload = part.get_payload(decode=True)
                return re.search(r'https?://\S+/authorize/restore_password/.+', payload.decode()).group(0)
        raise RuntimeError(f"Cannot get link to restore password from message {message_id}")

    def get_activation_link_from_message_within_timeout(self, email: str) -> str:
        timeout_sec = 90
        started_at = time.monotonic()
        while True:
            message_ids = self._list_message_ids(email, _ACTIVATE_YOUR_ACCOUNT_SUBJECT)
            if message_ids:
                [message_id] = message_ids
                [link, _] = self._get_message_link_and_code(message_id)
                return link
            if time.monotonic() - started_at > timeout_sec:
                raise RuntimeError(
                    "No activation letter received within %s seconds timeout", timeout_sec)
            time.sleep(0.5)

    def _get_message_link_and_code(self, message_id: str) -> Sequence[str]:
        response = self._call('uid', 'fetch', message_id, '(RFC822)')
        message = message_from_bytes(response[0][1])
        for part in message.walk():
            if part.get_content_type() == 'text/plain':
                payload = part.get_payload(decode=True)
                # Activation domain may not match account cloud host. Strange, yes.
                mo = re.search(r'https?://\S+/activate/(\w+(=|%3D){0,2})', payload.decode())
                if mo:
                    link = mo.group(0)
                    code = mo.group(1)
                    # An equals sign at the end of an encoded value can be escaped as "%3D".
                    code = unquote(code)
                    return link, code
        raise RuntimeError("No activation link is found in the letter")

    def _list_message_ids(self, email: str, subject: str) -> Sequence[str]:
        self._call('select')  # Google wants this to refresh search base
        search_criteria = f'(HEADER Subject "{subject!r}" TO "{email!r}")'
        [raw_ids] = self._call('uid', 'search', None, search_criteria)
        return sorted(raw_ids.decode('ascii').split(), key=int, reverse=True)

    def _call(self, fn_name, *args, **kw):
        fn = getattr(self._connection, fn_name)
        if fn_name == 'login':
            login, password = args
            masked_args = (login, '***')  # mask password
        else:
            masked_args = args
        masked_args = ' '.join(str(arg) for arg in (fn_name,) + masked_args)
        _logger.debug('\tIMAP: %s', masked_args)
        typ, dat = fn(*args, **kw)
        _logger.debug('\tIMAP: %s -> %r %r', masked_args, typ, dat)
        if typ != 'OK':
            raise RuntimeError(f"Request failed: {typ!r} {dat!r}")
        return dat
