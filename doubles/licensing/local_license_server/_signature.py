# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import hashlib
import logging
import os
from ctypes import CDLL
from ctypes import byref
from ctypes import c_char_p
from ctypes import c_int
from ctypes import c_size_t
from ctypes import c_void_p
from ctypes import create_string_buffer
from functools import lru_cache
from pathlib import Path
from typing import Union

_logger = logging.getLogger(__name__)


def sign(private_key_name: str, data: bytes):
    context = _sign_context(private_key_name)
    return context.sign(data)


@lru_cache()
def _sign_context(private_key_name: str) -> '_LicenseSignContext':
    root = Path(__file__).parent.parent.parent.parent.parent
    private_key_path = root / '_internal' / private_key_name
    return _LicenseSignContext(private_key_path)


class _LicenseSignContext:

    def __init__(self, path: Union[str, os.PathLike]):
        self._path = path
        pem = Path(path).read_bytes()
        key = _PrivateKey(pem)
        self._context = _SignContext(key)
        self._context.control('rsa_padding_mode', 'pkcs1')

    def __repr__(self):
        return f'{self.__class__.__name__}({self._path!r})'

    def sign(self, data: bytes) -> bytes:
        digest = hashlib.sha1(data).digest()
        return self._context.sign(digest)


class _SignContext:

    def __init__(self, key: '_PrivateKey'):
        self._ptr = None  # In case __init__ fails
        self._ptr = _lib.EVP_PKEY_CTX_new(key.ptr, None)
        _lib.EVP_PKEY_sign_init(self._ptr)

    def __del__(self):
        _lib.EVP_PKEY_CTX_free(self._ptr)

    def control(self, param: str, value: str) -> None:
        _lib.EVP_PKEY_CTX_ctrl_str(self._ptr, param.encode(), value.encode())

    def sign(self, digest: bytes) -> bytes:
        size = c_size_t()
        _lib.EVP_PKEY_sign(self._ptr, None, byref(size), digest, len(digest))
        buf = create_string_buffer(size.value)
        _lib.EVP_PKEY_sign(self._ptr, buf, byref(size), digest, len(digest))
        return buf.raw


class _PrivateKey:

    def __init__(self, pem: bytes):
        self.ptr = None  # In case __init__ fails
        bio = _BinaryIO()
        bio.write(pem)
        self.ptr = _lib.PEM_read_bio_PrivateKey(bio.ptr, None, None, None)

    def __del__(self):
        _lib.EVP_PKEY_free(self.ptr)


class _BinaryIO:

    def __init__(self):
        self.ptr = None  # In case __init__ fails
        self.ptr = _lib.BIO_new(_lib.BIO_s_mem())

    def write(self, buf: bytes) -> int:
        written = _lib.BIO_write(self.ptr, c_char_p(buf), len(buf))
        if written != len(buf):
            raise RuntimeError(f"Wrote only {written} of {len(buf)} to BIO")
        return written

    def __del__(self):
        _lib.BIO_vfree(self.ptr)


def _bytes_written(result, _func, _args):
    if result >= 0:
        return result
    raise _LastOpenSslError()


def _must_be_positive(result, _func, _args):
    if result <= 0:
        raise _LastOpenSslError()


def _must_be_1(result, _func, _args):
    if result != 1:
        raise _LastOpenSslError()


def _must_not_be_null(result, _func, _args):
    if result is not None:
        return result
    raise _LastOpenSslError()


class _LastOpenSslError(Exception):

    def __init__(self):
        code = _lib.ERR_get_error()
        buf = create_string_buffer(256)
        _lib.ERR_error_string_n(code, buf, len(buf))
        super().__init__(buf.value.decode())


if os.name == 'nt':
    _lib = CDLL('libcrypto')  # Part of OpenSSL
else:
    for lib_file in ['libcrypto.so', 'libcrypto.so.3', 'libcrypto.so.2', 'libcrypto.so.1.1']:
        try:
            _lib = CDLL(lib_file)  # Part of OpenSSL
            break
        except OSError as e:
            if 'No such file or directory' not in str(e):
                raise
            _logger.info("File %s not found in system", lib_file)
    else:
        raise RuntimeError("No version of libcrypto.so found in system")
# See: https://www.openssl.org/docs
# See: https://github.com/openssl/openssl/blob/master/include/openssl/rsa.h
# See: https://github.com/openssl/openssl/blob/master/include/openssl/evp.h
# See: https://github.com/openssl/openssl/blob/master/crypto/rsa/rsa_lib.c
_lib.EVP_PKEY_CTX_new.restype = c_void_p
_lib.EVP_PKEY_CTX_new.argtypes = [c_void_p, c_void_p]
_lib.EVP_PKEY_CTX_new.errcheck = _must_not_be_null
_lib.EVP_PKEY_CTX_free.restype = None
_lib.EVP_PKEY_CTX_free.argtypes = [c_void_p]
_lib.EVP_PKEY_sign_init.restype = c_int
_lib.EVP_PKEY_sign_init.argtypes = [c_void_p]
_lib.EVP_PKEY_sign_init.errcheck = _must_be_1
_lib.EVP_PKEY_CTX_ctrl_str.restype = c_int
_lib.EVP_PKEY_CTX_ctrl_str.argtypes = [c_void_p, c_char_p, c_char_p]
_lib.EVP_PKEY_CTX_ctrl_str.errcheck = _must_be_positive
_lib.EVP_PKEY_sign.restype = c_int
_lib.EVP_PKEY_sign.argtypes = [c_void_p, c_void_p, c_void_p, c_void_p, c_void_p]
_lib.EVP_PKEY_sign.errcheck = _must_be_1
_lib.PEM_read_bio_PrivateKey.restype = c_void_p
_lib.PEM_read_bio_PrivateKey.argtypes = [c_void_p, c_void_p, c_void_p, c_void_p]
_lib.PEM_read_bio_PrivateKey.errcheck = _must_not_be_null
_lib.EVP_PKEY_free.restype = None
_lib.EVP_PKEY_free.argtypes = [c_void_p]
_lib.BIO_s_mem.restype = c_void_p
_lib.BIO_s_mem.argtypes = []
_lib.BIO_s_mem.errcheck = _must_not_be_null
_lib.BIO_new.restype = c_void_p
_lib.BIO_new.argtypes = [c_void_p]
_lib.BIO_new.errcheck = _must_not_be_null
_lib.BIO_write.restype = c_int
_lib.BIO_write.argtypes = [c_void_p, c_void_p, c_int]
_lib.BIO_write.errcheck = _bytes_written
_lib.BIO_vfree.restype = None
_lib.BIO_vfree.argtypes = [c_void_p]


def test_correctness():
    lipsum = b'bla-bla-bla' * 100500

    context = _sign_context()
    for _ in range(10):  # Check that context doesn't change its state
        context.sign(lipsum)
    signature = context.sign(lipsum)
    print(signature)
    # Use cryptography to verify only. Don't require it for normal work.
    from cryptography.hazmat.primitives.asymmetric.padding import PKCS1v15
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    public_path = Path(__file__).absolute().parent / 'key.pub'
    public = load_pem_public_key(public_path.read_bytes())
    decrypted = public.recover_data_from_signature(signature, PKCS1v15(), None)
    print(decrypted)
    assert decrypted == hashlib.sha1(lipsum).digest()


if __name__ == '__main__':
    test_correctness()
