# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
r"""Simple, persistent certificate authority.

>>> from subprocess import PIPE
>>> from subprocess import run
>>> openssl = 'openssl' if os.name != 'nt' else r'C:\Program Files\Git\usr\bin\openssl.exe'
>>> run([openssl, 'x509', '-checkend', '0', '-in', default_ca().cert_path], stdout=PIPE)  # doctest: +ELLIPSIS
CompletedProcess(...returncode=0...)
>>> contents = default_ca().generate_key_and_cert('127.0.0.1').encode()
>>> run([openssl, 'verify', '-CAfile', default_ca().cert_path], input=contents, stdout=PIPE)  # doctest: +ELLIPSIS
CompletedProcess(...returncode=0...)
>>> # Modulus and public exponent must match.
>>> # Public exponent is hard to retrieve and almost always 65537.
>>> key_modulus = run([openssl, 'rsa', '-modulus', '-noout'], input=contents, stdout=PIPE)
>>> cert_modulus = run([openssl, 'x509', '-modulus', '-noout'], input=contents, stdout=PIPE)
>>> key_modulus.stdout  # doctest: +ELLIPSIS
b'Modulus=...'
>>> key_modulus.stdout == cert_modulus.stdout
True
"""

import logging
import os
import socket
import ssl
import time
from contextlib import AbstractContextManager
from contextlib import contextmanager
from datetime import datetime
from functools import lru_cache
from ipaddress import AddressValueError
from ipaddress import IPv4Address
from pathlib import Path
from tempfile import mkstemp
from typing import Collection
from typing import Iterable

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


@lru_cache()
def default_ca():
    return CA(Path('~/.cache/nx-func-tests-ca').expanduser())


class CA:
    """CertificateAuthority."""

    def __init__(self, ca_dir: Path):
        ca_dir.mkdir(exist_ok=True)
        self.cert_path = ca_dir / 'ca.crt'
        key_path = ca_dir / 'ca.key'
        if not self.cert_path.exists() or not key_path.exists():
            _logger.debug("Generating new CA certificate %s and key %s...", self.cert_path, key_path)
            self._key, key_pem = _generate_key()
            key_path.write_bytes(key_pem)
            self._cert = _generate_ca_cert(self._key)
            certificate_string = self._cert.public_bytes(serialization.Encoding.PEM)
            self.cert_path.write_bytes(certificate_string)
            _logger.info("New CA certificate %s can be added to browser or system as trusted.", self.cert_path)
        else:
            certificate_string = self.cert_path.read_bytes()
            self._cert = x509.load_pem_x509_certificate(certificate_string, default_backend())
            key_pem = key_path.read_bytes()
            self._key = serialization.load_pem_private_key(key_pem, None, default_backend())

    def generate_key_and_cert(self, *hostnames: str):
        key, cert = self.generate_key_and_cert_pair(*hostnames)
        return key + cert

    def generate_key_and_cert_pair(self, *hostnames: str):
        _logger.debug("Generating key...")
        client_key, client_key_pem = _generate_key()
        _logger.debug("Making certificate...")
        cert = _generate_client_cert(client_key, self._key, self._cert.subject, hostnames)
        cert_pem = cert.public_bytes(serialization.Encoding.PEM)
        return client_key_pem.decode(), cert_pem.decode()

    def wrap_client_socket(self, sock: socket.socket) -> ssl.SSLSocket:
        ssl_context = ssl.SSLContext(protocol=ssl.PROTOCOL_TLS_CLIENT)
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.VerifyMode.CERT_REQUIRED
        ssl_context.load_verify_locations(
            cadata=self._cert.public_bytes(serialization.Encoding.DER),
            )
        ssl_context.keylog_filename = os.environ.get('SSLKEYLOGFILE')
        return ssl_context.wrap_socket(sock)

    def wrap_server_socket(self, sock: socket.socket, hostnames: Collection[str]) -> ssl.SSLSocket:
        ssl_context = ssl.SSLContext(protocol=ssl.PROTOCOL_TLS_SERVER)
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.VerifyMode.CERT_NONE
        server_key, server_key_pem = _generate_key()
        server_cert = _generate_client_cert(server_key, self._key, self._cert.subject, hostnames)
        server_cert_pem = server_cert.public_bytes(serialization.Encoding.PEM)
        # Certificate chains can't be loaded from memory.
        # See: https://github.com/python/cpython/issues/60691
        with _as_temp_file(server_key_pem + server_cert_pem) as pem_file:
            ssl_context.load_cert_chain(pem_file)
        ssl_context.keylog_filename = os.environ.get('SSLKEYLOGFILE')
        return ssl_context.wrap_socket(sock, server_side=True)

    def add_to_env_vars(self):
        """Make it trusted in this process.

        curl respects CURL_CA_BUNDLE.
        pip respects CURL_CA_BUNDLE and REQUESTS_CA_BUNDLE.
        requests respects CURL_CA_BUNDLE and REQUESTS_CA_BUNDLE.
        """
        os.environ['FT_CA_BUNDLE'] = str(self.cert_path)


def _generate_key():
    key = rsa.generate_private_key(65537, 2048, default_backend())
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption())
    return key, pem


def _generate_ca_cert(key):
    usage = x509.KeyUsage(
        digital_signature=False,
        content_commitment=False,
        key_encipherment=False,
        data_encipherment=False,
        key_agreement=False,
        key_cert_sign=True,
        crl_sign=False,
        encipher_only=False,
        decipher_only=False,
        )
    ski = x509.SubjectKeyIdentifier.from_public_key(key.public_key())
    aki = x509.AuthorityKeyIdentifier.from_issuer_subject_key_identifier(ski)
    ca_constraints = x509.BasicConstraints(ca=True, path_length=1)
    serial = x509.random_serial_number()
    name = x509.Name([
        x509.NameAttribute(x509.NameOID.COUNTRY_NAME, 'US'),
        x509.NameAttribute(x509.NameOID.ORGANIZATION_NAME, 'NetworkOptix'),
        x509.NameAttribute(x509.NameOID.ORGANIZATIONAL_UNIT_NAME, "FT"),
        # Serial number is included for a reason:
        # If CA certificate is added into trusted storage (at least on Windows)
        # and then re-generated by this component,
        # TLS handshake finds old CA certificate stored in the trusted storage
        # instead of current CA certificate,
        # despite the fact that the latter is explicitly added to SSL context.
        x509.NameAttribute(x509.NameOID.COMMON_NAME, f"FT Root CA for Tests Only, Auto-Generated, {serial:040X}"),
        ])
    cert = (
        x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .not_valid_before(datetime(2020, 1, 1))
            .not_valid_after(datetime(2030, 1, 1))
            .serial_number(serial)
            .public_key(key.public_key())
            .add_extension(ca_constraints, critical=True)
            .add_extension(usage, critical=True)
            .add_extension(ski, critical=False)
            .add_extension(aki, critical=False)
            .sign(key, hashes.SHA256(), default_backend()))
    return cert


def _generate_client_cert(client_key, ca_key, ca_name, hostnames: Iterable[str]):
    alternative_entries = {x509.DNSName('localhost'), x509.IPAddress(IPv4Address('127.0.0.1'))}
    for hostname in hostnames:
        try:
            ip = IPv4Address(hostname)
        except AddressValueError:
            alternative_entries.add(x509.DNSName(hostname))
            alternative_entries.add(x509.IPAddress(IPv4Address(get_host_by_name(hostname))))
        else:
            alternative_entries.add(x509.IPAddress(ip))
    alt_names = x509.SubjectAlternativeName(alternative_entries)
    usage = x509.KeyUsage(
        digital_signature=True,
        content_commitment=False,
        key_encipherment=False,
        data_encipherment=False,
        # Key Agreement purpose required by ffprobe. Without it ffprobe returns
        # the TLS error: "Key usage violation in certificate has been detected".
        key_agreement=True,
        key_cert_sign=False,
        crl_sign=False,
        encipher_only=False,
        decipher_only=False,
        )
    ext_usage = x509.ExtendedKeyUsage([x509.ExtendedKeyUsageOID.SERVER_AUTH])
    ca_constraints = x509.BasicConstraints(ca=False, path_length=None)
    name = x509.Name([
        *ca_name.get_attributes_for_oid(x509.NameOID.COUNTRY_NAME),
        *ca_name.get_attributes_for_oid(x509.NameOID.ORGANIZATION_NAME),
        *ca_name.get_attributes_for_oid(x509.NameOID.ORGANIZATIONAL_UNIT_NAME),
        x509.NameAttribute(x509.NameOID.COMMON_NAME, "FT for Tests Only"),
        ])
    cert = (
        x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(ca_name)
            .not_valid_before(datetime(2020, 1, 1))
            .not_valid_after(datetime(2030, 1, 1))
            .serial_number(x509.random_serial_number())
            .public_key(client_key.public_key())
            .add_extension(alt_names, critical=True)
            .add_extension(ca_constraints, critical=True)
            .add_extension(usage, critical=True)
            .add_extension(ext_usage, critical=True)
            .sign(ca_key, hashes.SHA256(), default_backend()))
    return cert


@lru_cache()
def get_host_by_name(hostname):
    for _ in range(3):
        try:
            return socket.gethostbyname(hostname)
        except socket.gaierror:
            _logger.debug("Failed to get ip by name {}".format(hostname))
            time.sleep(1)
    return socket.gethostbyname(hostname)


@contextmanager
def _as_temp_file(data: bytes) -> AbstractContextManager[Path]:
    # We can't use tempfile.NamedTemporaryFile() due to windows-related bug
    # See: https://github.com/python/cpython/issues/66305
    fd, path = mkstemp(suffix='.pem')
    path = Path(path)
    data = memoryview(data)
    try:
        while data:
            written = os.write(fd, data)
            data = data[written:]
        os.close(fd)
        yield path
    finally:
        path.unlink(missing_ok=True)


_logger = logging.getLogger(__name__)
