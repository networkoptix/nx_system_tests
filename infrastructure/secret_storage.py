# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import argparse
import hashlib
import logging
import os
from abc import ABCMeta
from abc import abstractmethod
from pathlib import Path
from typing import Optional

import requests
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.hazmat.primitives.serialization import PublicFormat
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.hazmat.primitives.serialization import load_ssh_private_key
from cryptography.hazmat.primitives.serialization import load_ssh_public_key

from config import global_config

_logger = logging.getLogger(__name__)


def _encrypt_data(data: str, public_key) -> bytes:
    return public_key.encrypt(data.encode(encoding='ascii'), padding=padding.PKCS1v15())


def _decrypt_data(encrypted_data: bytes, private_key) -> bytes:
    return private_key.decrypt(encrypted_data, padding=padding.PKCS1v15())


def _get_public_key_fingerprint(public_key):
    public_data = public_key.public_bytes(
        encoding=Encoding.DER,
        format=PublicFormat.SubjectPublicKeyInfo)
    return hashlib.sha1(public_data).hexdigest()


class SecretNotFound(Exception):

    def __init__(self, name):
        super().__init__(f"Secret {name} not found")


_PRIVATE_KEY_PATH_PARAMETER_NAME = 'private_key_path'


class PrivateKeyFileNotFound(Exception):

    def __init__(self, key_path):
        super().__init__(
            "Private key file required to decrypt secret is missing. "
            f"Make sure the {key_path} file exists or specify a different path through "
            f"the {_PRIVATE_KEY_PATH_PARAMETER_NAME} parameter in the default settings file")


_PRIVATE_KEY_PASSWORD_ENV_NAME = 'PRIVATE_KEY_PASSWORD'


class _EmptyPrivateKeyPassword(Exception):

    def __init__(self):
        super().__init__(
            "The file is password protected. Set the password "
            f"in the {_PRIVATE_KEY_PASSWORD_ENV_NAME} environment variable")


class _LoadPrivateKeyError(Exception):

    def __init__(self):
        super().__init__("Seems like the password is incorrect")


class SecretStorage(metaclass=ABCMeta):

    def __init__(self, private_key_path: Path):
        try:
            self._private_key = self._load_private_key(private_key_path)
        except (_EmptyPrivateKeyPassword, _LoadPrivateKeyError) as e:
            raise RuntimeError(f"Failed to load {private_key_path}: {e}")
        self._public_key_fingerprint = _get_public_key_fingerprint(self._private_key.public_key())

    def _load_private_key(self, private_key_path):
        data = private_key_path.read_bytes()
        password = os.environ.get(_PRIVATE_KEY_PASSWORD_ENV_NAME)
        if password is not None:
            password = password.encode()
        if data.startswith(b'-----BEGIN OPENSSH PRIVATE KEY-----'):
            _logger.debug("Loading SSH private key %s", private_key_path)
            return self._load_ssh_private_key(data, password)
        _logger.debug("Loading PEM private key %s", private_key_path)
        return self._load_pem_private_key(data, password)

    @staticmethod
    def _load_ssh_private_key(data: bytes, password: Optional[bytes]):
        try:
            return load_ssh_private_key(data, password)
        except ValueError as e:
            if 'Key is password-protected' in str(e):
                raise _EmptyPrivateKeyPassword()
            if 'Corrupt data: broken checksum' in str(e):
                raise _LoadPrivateKeyError()
            raise

    @staticmethod
    def _load_pem_private_key(data: bytes, password: Optional[bytes]):
        try:
            return load_pem_private_key(data, password)
        except TypeError as e:
            if 'Password was not given but private key is encrypted' in str(e):
                raise _EmptyPrivateKeyPassword()
            raise
        except ValueError as e:
            if 'Bad decrypt' in str(e):
                raise _LoadPrivateKeyError()
            raise

    def get(self, name: str) -> bytes:
        encrypted_data = self._get_encrypted_secret(name)
        return _decrypt_data(encrypted_data, self._private_key)

    @abstractmethod
    def _get_encrypted_secret(self, name: str) -> bytes:
        pass


class _FileSecretStorage(SecretStorage):

    def __init__(self, storage_url, private_key_path):
        super().__init__(private_key_path)
        self._storage_url = storage_url

    def _get_encrypted_secret(self, name):
        # Files for each private key are placed in their own directory.
        file_url = f'{self._storage_url}/{self._public_key_fingerprint}/{name}.enc'
        _logger.debug("Getting file %s", file_url)
        try:
            response = requests.get(file_url)
        except (requests.ConnectionError, requests.HTTPError) as e:
            raise RuntimeError(f"Failed to get file {file_url}: {e}")
        if response.status_code == 200:
            return response.content
        if response.status_code == 404:
            raise SecretNotFound(name)
        raise RuntimeError(
            f"Failed to get file {file_url}: {response.status_code} {response.reason}")


def _encrypt_file(file_path: Path, public_key_path: Path):
    text = file_path.read_text(encoding='ascii')
    public_key_data = public_key_path.read_bytes()
    if public_key_data.startswith(b'-----BEGIN PUBLIC KEY-----'):
        public_key = load_pem_public_key(public_key_data)
    else:
        public_key = load_ssh_public_key(public_key_data)
    public_key_fingerprint = _get_public_key_fingerprint(public_key)
    encrypted_data = _encrypt_data(text, public_key)
    encrypted_file_path = file_path.with_suffix('.enc')
    encrypted_file_path.write_bytes(encrypted_data)
    _logger.info(
        "File %s for public key with fingerprint %s was successfully encrypted into %s",
        file_path.name, public_key_fingerprint, encrypted_file_path.name)


def _parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--file-path', type=Path, required=True, help="File to encrypt.")
    parser.add_argument(
        '--public-key-path',
        default=Path('~/.ssh/id_rsa.pub').expanduser(),
        help="Path to the public key file (SSH or PEM). If not specified, ~/.ssh/id_rsa.pub is used.")
    return parser.parse_args()


_DEFAULT_PRIVATE_KEY_PATH = '~/.ssh/id_rsa'

_secret_storage: Optional[SecretStorage] = None


def get_secret(name: str) -> bytes:
    global _secret_storage
    if _secret_storage is None:
        storage_url = global_config['secret_storage_url']
        private_key_path = global_config.get(
            _PRIVATE_KEY_PATH_PARAMETER_NAME, _DEFAULT_PRIVATE_KEY_PATH)
        private_key_path = Path(private_key_path).expanduser()
        if not private_key_path.exists():
            raise PrivateKeyFileNotFound(private_key_path)
        _secret_storage = _FileSecretStorage(storage_url, private_key_path)
    return _secret_storage.get(name)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    parsed_args = _parse_args()
    _encrypt_file(parsed_args.file_path, parsed_args.public_key_path)
