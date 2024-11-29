# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import logging
import time
from base64 import urlsafe_b64encode
from collections.abc import Mapping
from collections.abc import Sequence
from functools import lru_cache
from typing import Any

import requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_private_key


class GoogleAuthProvider:

    def __init__(self, credentials: Mapping[str, Any]):
        # See: https://developers.google.com/sheets/api/quickstart/python#authorize_credentials_for_a_desktop_application
        self._credentials = credentials

    def get_access_token(self, scope: str, lifetime_duration: int) -> str:
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            }
        data = {
            'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
            'assertion': self._create_jwt_token(scope, lifetime_duration),
            }
        response = requests.post(self._credentials['token_uri'], headers=headers, data=data)
        response_data = response.json()
        if 'access_token' in response_data:
            return response_data['access_token']
        else:
            raise RuntimeError(f"Failed to get access token: {response_data!r}")

    def _create_jwt_token(self, scope: str, lifetime_duration: int) -> str:
        header = {
            'alg': 'RS256',
            'typ': 'JWT',
            }
        now = int(time.time())
        payload = {
            'iss': self._credentials['client_email'],
            'scope': scope,
            'aud': self._credentials['token_uri'],
            'iat': now,
            'exp': now + lifetime_duration,
            }
        rsa_key = load_pem_private_key(self._credentials['private_key'].encode('ascii'), password=None)
        json_header = json.dumps(header).encode('ascii')
        json_payload = json.dumps(payload).encode('ascii')
        body = _base64url_encode(json_header) + b'.' + _base64url_encode(json_payload)
        signature = rsa_key.sign(body, padding.PKCS1v15(), hashes.SHA256())
        jwt_token = body + b'.' + _base64url_encode(signature)
        return jwt_token.decode('ascii')


class GoogleSheet:
    # See: https://developers.google.com/sheets/api
    _SCOPE = 'https://www.googleapis.com/auth/spreadsheets'
    _BASE_URL = 'https://sheets.googleapis.com/v4/spreadsheets'

    def __init__(self, auth_provider: GoogleAuthProvider):
        self._auth_provider = auth_provider

    def write(self, document_id: str, sheet_name: str, range_name: str, data: Sequence[Mapping[str, Any]]):
        rows = [list(row.values()) for row in data]  # Value cells.
        rows.insert(0, list(data[0].keys()))  # Header cells.
        response = requests.post(
            f'{self._BASE_URL}/{document_id}/values/{sheet_name}!A1:Z99999:clear',
            headers=self._get_auth_header(),
            )
        _logger.info("Spreadsheet %s has been cleared (%r)", sheet_name, response.json())
        response = requests.post(
            f'{self._BASE_URL}/{document_id}/values/{sheet_name}!{range_name}:append?valueInputOption=RAW',
            headers=self._get_auth_header(),
            json={'values': rows},
            )
        if 200 <= response.status_code <= 299:
            _logger.info("Data have been written to the spreadsheet %s (%r)", sheet_name, response.json())
            _logger.info("Spreadsheet URL: https://docs.google.com/spreadsheets/d/%s", document_id)
        else:
            raise RuntimeError(f"Failed to write data to the spreadsheet ({response.text})")

    @lru_cache
    def _get_auth_header(self) -> Mapping[str, str]:
        return {
            'Authorization': f'Bearer {self._auth_provider.get_access_token(self._SCOPE, 120)}',
            'Content-Type': 'application/json',
            }


def _base64url_encode(data: bytes) -> bytes:
    return urlsafe_b64encode(data).rstrip(b'=')


_logger = logging.getLogger(__name__)
