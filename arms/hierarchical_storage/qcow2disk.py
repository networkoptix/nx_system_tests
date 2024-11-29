# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
# See: https://github.com/qemu/qemu/blob/master/docs/interop/qcow2.txt
import copy
import logging
import os
import struct
import time
from abc import ABCMeta
from abc import abstractmethod
from contextlib import AbstractContextManager
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO
from typing import Iterator
from typing import List
from typing import Sequence
from typing import TypeVar


class QCOW2Disk:

    def __init__(self, path: Path):
        if path.suffix != '.qcow2':
            raise RuntimeError(f"{path} does not have a proper extension '.qcow2'")
        self._path = path

    def get_child(self, path: Path) -> 'QCOW2ChildDisk':
        return QCOW2ChildDisk(path=path, parent_path=self._path)

    def __repr__(self):
        return f'<QCOW2: {self._path}>'


class QCOW2ChildDisk(QCOW2Disk):

    def __init__(self, path: Path, parent_path: Path):
        super().__init__(path)
        self._parent_path = parent_path

    @contextmanager
    def _opened_path(self) -> AbstractContextManager[BinaryIO]:
        try:
            with self._path.open('xb') as fd:
                yield fd
        except FileExistsError:
            raise DiskExists(f"{self}: Already exists")

    def _absolute_parent_path(self) -> Path:
        if self._parent_path.is_absolute():
            return self._parent_path
        return self._path.parent.joinpath(self._parent_path)

    def create(self):
        with self._opened_path() as fd:
            with self._absolute_parent_path().open('rb') as parent_fd:
                _update_access_time(parent_fd.fileno())
                parent_header = _HeaderV3.read(parent_fd)
            child_header = parent_header.copy_without_extensions()
            child_header.set_parent(str(self._parent_path))
            clusters = child_header.clustered(fd)
            header_cluster = next(clusters)
            header_cluster.allocate()
            l1_table_cluster = next(clusters)
            l1_table_cluster.allocate()
            refcount_l1_cluster = next(clusters)
            refcount_l1_cluster.allocate()
            refcount_l2_cluster = next(clusters)
            refcount_l2_cluster.allocate()
            child_header.set_l1_table_offset(l1_table_cluster.get_offset())
            child_header.set_refcount_table_offset(refcount_l1_cluster.get_offset())
            l2_refcount_table_offset_raw = refcount_l2_cluster.get_offset().to_bytes(
                length=8,
                byteorder="big",
                signed=False,
                )
            refcount_l1_cluster.write(l2_refcount_table_offset_raw)
            header_cluster.write(child_header.as_bytes())
            clusters.commit_refcount_table(refcount_l2_cluster)
        logging.info("%r: Created successfully", self)

    def remove(self):
        self._path.unlink(missing_ok=True)

    def __repr__(self):
        return f'<QCOW2: {self._path}, parent={self._parent_path}>'


def _update_access_time(fileno: int):
    atime_ns = time.time_ns()
    mtime_ns = os.stat(fileno).st_mtime_ns
    os.utime(fileno, ns=(atime_ns, mtime_ns))


class DiskExists(Exception):
    pass


class _HeaderV3:

    _format = "!IIQIIQIIQQIIQQQQII"
    _format_size = struct.calcsize(_format)
    _magic = 0x514649fb
    _qcow2_version = 3
    _crypt_method = 0
    _nb_snapshots = 0
    _snapshots_offset = 0
    _incompatible_features = 0
    _compatible_features = 0
    _autoclear_features = 0
    _compression_type = 0

    def __init__(self, cluster_bits: int, refcount_order: int):
        self._cluster_bits = cluster_bits
        self._size_bytes = 0
        self._l1_size = 0
        self._l1_table_offset = 0
        self._refcount_table_offset = 0
        self._refcount_table_clusters = 0
        self._refcount_order = refcount_order
        self._extensions: List[_Extension] = []
        self._backing_file_path = ''

    def clustered(self, fd: BinaryIO) -> '_Clustered':
        cluster_size = self._get_cluster_size()
        refcount_table = _RefcountTable(self._refcount_order)
        return _Clustered(fd, cluster_size, refcount_table)

    def _get_cluster_size(self) -> int:
        return 1 << self._cluster_bits

    def set_parent(self, path: str):
        self._backing_file_path = path

    @classmethod
    def read(cls, fd: BinaryIO):
        header_raw = fd.read(cls._format_size)
        [
            magic,
            version,
            backing_file_offset,
            backing_file_size,
            cluster_bits,
            size_bytes,
            crypt_method,
            l1_size,
            l1_table_offset,
            refcount_table_offset,
            refcount_table_clusters,
            nb_snapshots,
            snapshots_offset,
            incompatible_features,
            compatible_features,
            autoclear_features,
            refcount_order,
            header_length,
            ] = struct.unpack(cls._format, header_raw)
        if magic != cls._magic:
            raise RuntimeError(f"Wrong magic. Got {magic}. Expected {cls._magic}")
        if version != 3:
            raise RuntimeError(f"Unsupported QCOW version {version}")
        header = cls(cluster_bits, refcount_order)
        header._size_bytes = size_bytes
        if crypt_method != cls._crypt_method:
            raise RuntimeError(f"Unknown crypt method {crypt_method}")
        header._l1_table_offset = l1_table_offset
        header._l1_size = l1_size
        header._refcount_table_offset = refcount_table_offset
        header._refcount_table_clusters = refcount_table_clusters
        if nb_snapshots != cls._nb_snapshots or snapshots_offset != cls._snapshots_offset:
            raise RuntimeError("Snapshots configuration is not supported")
        if incompatible_features != 0:
            raise RuntimeError(f"Incompatible features is not empty: 0x{incompatible_features:x}")
        if compatible_features != 0:
            raise RuntimeError(f"Compatible features is not empty: 0x{compatible_features:x}")
        if autoclear_features != 0:
            raise RuntimeError(f"Autoclear features is not empty: 0x{autoclear_features:x}")
        to_read = header_length - cls._format_size
        if to_read > 0:
            optional_data = fd.read(to_read)
            if to_read != 8:
                raise RuntimeError(f"Unknown data is present in a header: {optional_data}")
            compression_type = optional_data[-1]
            if compression_type != cls._compression_type:
                raise RuntimeError(f"Unsupported compression type: 0x{compression_type:x}")
        for extension in _read_extensions(fd):
            header._extensions.append(extension)
        if backing_file_offset > 0:
            fd.seek(backing_file_offset)
            backing_file = fd.read(backing_file_size)
            header._backing_file_path = backing_file.decode('utf-8')
        return header

    def as_bytes(self) -> bytes:
        extensions = [*self._extensions, _EndOfExtensions()]
        extensions_raw = b''.join(extension.as_bytes() for extension in extensions)
        buffer = bytearray(self._format_size) + extensions_raw
        backing_file_offset = backing_file_path_size = 0
        if self._backing_file_path:
            backing_file_offset = len(buffer)
            backing_file = self._backing_file_path.encode('utf-8')
            backing_file_path_size = len(backing_file)
            buffer.extend(backing_file)
        struct.pack_into(
            self._format,
            buffer,
            0,
            self._magic,
            self._qcow2_version,
            backing_file_offset,
            backing_file_path_size,
            self._cluster_bits,
            self._size_bytes,
            self._crypt_method,
            self._l1_size,
            self._l1_table_offset,
            self._refcount_table_offset,
            self._refcount_table_clusters,
            self._nb_snapshots,
            self._snapshots_offset,
            self._incompatible_features,
            self._compatible_features,
            self._autoclear_features,
            self._refcount_order,
            self._format_size,
            )
        return bytes(buffer)

    def set_l1_table_offset(self, offset: int):
        self._l1_table_offset = offset

    def set_refcount_table_offset(self, offset: int):
        self._refcount_table_offset = offset

    def copy_without_extensions(self) -> '_HeaderV3':
        # TODO: Implement extensions parsing for qcow2target
        header_copy = copy.deepcopy(self)
        header_copy._extensions.clear()
        return header_copy


class _RefcountTable:

    def __init__(self, refcount_order: int):
        refcount_bits = 1 << refcount_order
        self._refcount_block_bytes = refcount_bits // 8
        self._counters: List[_ReferenceCounter] = []

    def get_reference(self) -> '_ReferenceCounter':
        reference_counter = _ReferenceCounter(self._refcount_block_bytes)
        self._counters.append(reference_counter)
        return reference_counter

    def as_bytes(self) -> bytes:
        return b''.join(counter.as_bytes() for counter in self._counters)


class _ReferenceCounter:

    def __init__(self, refcount_block_bytes: int):
        self._refcount_block_size_bytes = refcount_block_bytes
        self._value = 0

    def set_used(self):
        self._value = 1

    def as_bytes(self) -> bytes:
        return self._value.to_bytes(self._refcount_block_size_bytes, byteorder="big", signed=False)


class _HostCluster:

    # TODO: Create an OS-agnostic fallocate wrapper and pass there
    #  a mmap object instead of (fd + offset + size)
    def __init__(
            self,
            fd: BinaryIO,
            cluster_size_bytes: int,
            cluster_offset: int,
            references_counter: _ReferenceCounter,
            ):
        self._fd = fd
        self._cluster_size_bytes = cluster_size_bytes
        self._cluster_offset = cluster_offset
        self._references_counter = references_counter

    def get_offset(self) -> int:
        return self._cluster_offset

    def allocate(self):
        self._references_counter.set_used()
        self._fd.seek(self._cluster_offset)
        self._fd.write(b'\x00' * self._cluster_size_bytes)

    def write(self, raw: bytes):
        if len(raw) > self._cluster_size_bytes:
            raise RuntimeError(
                f"Cluster size is {self._cluster_size_bytes} but attempted to write {len(raw)}")
        self._references_counter.set_used()
        self._fd.seek(self._cluster_offset)
        self._fd.write(raw)


class _Clustered(Iterator[_HostCluster]):

    def __init__(self, fd: BinaryIO, cluster_size_bytes: int, refcount_table: '_RefcountTable'):
        self._fd = fd
        self._cluster_size_bytes = cluster_size_bytes
        self._refcount_table = refcount_table
        self._offset = 0

    def __next__(self):
        refcount = self._refcount_table.get_reference()
        cluster_offset = self._offset
        self._offset += self._cluster_size_bytes
        return _HostCluster(self._fd, self._cluster_size_bytes, cluster_offset, refcount)

    def commit_refcount_table(self, cluster: _HostCluster):
        cluster.write(self._refcount_table.as_bytes())


class _Extension(metaclass=ABCMeta):

    type: int

    def as_bytes(self) -> bytes:
        raw_data = self._get_raw()
        data_length = len(raw_data)
        suffix_length = data_length % 8
        extension_format = f"!II{data_length}s"
        length = struct.calcsize(extension_format) + suffix_length
        result = struct.pack(extension_format, self.type, data_length, raw_data)
        return result.ljust(length, b'\x00')

    @abstractmethod
    def _get_raw(self) -> bytes:
        pass

    @classmethod
    @abstractmethod
    def from_raw(cls, data: bytes) -> '_Extension':
        pass

    @abstractmethod
    def __repr__(self):
        pass


_extensions: dict[int, type[_Extension]] = {}
_T = TypeVar('_T', bound=type[_Extension])


def _register_extension(cls: _T) -> _T:
    try:
        cls_type = cls.type
    except AttributeError:
        raise RuntimeError(
            f"Class {cls} must have integer attribute 'type' set to an appropriate integer value")
    _extensions[cls_type] = cls
    return cls


def _read_extensions(fd: BinaryIO) -> Sequence[_Extension]:
    extensions = []
    while True:
        extension_type, extension_data_length = struct.unpack('!II', fd.read(8))
        extension_class = _extensions.get(extension_type)
        extension_data = fd.read(extension_data_length)
        if extension_class is None:
            logging.warning("Ignore unknown exception 0x%x", extension_type)
            continue
        extension = extension_class.from_raw(extension_data)
        extensions.append(extension)
        if extension.type == 0x0:
            return extensions
        non_rounded_suffix = extension_data_length % 8
        if non_rounded_suffix > 0:
            fd.read(8 - non_rounded_suffix)


@_register_extension
class _EndOfExtensions(_Extension):

    type = 0x0

    def _get_raw(self):
        return b''

    @classmethod
    def from_raw(cls, data: bytes):
        if data:
            raise RuntimeError(f"Non-zero data: {data!r}")
        return cls()

    def __repr__(self):
        return '<EnfOfExtensions>'


@_register_extension
class _BackingFileFormat(_Extension):

    type = 0xe2792aca

    def __init__(self, format_: str):
        self._format = format_

    def _get_raw(self):
        return self._format.encode('utf-8')

    @classmethod
    def from_raw(cls, data: bytes):
        return cls(data.decode('utf-8'))

    def __repr__(self):
        return f'<BackingFormat: {self._format}>'


_feature_format = '!BB46s'
_feature_format_size = struct.calcsize(_feature_format)


class _Feature:

    name: str
    type: int
    bit_number: int

    def as_bytes(self) -> bytes:
        encoded_name = self.name.encode('utf-8')
        result = struct.pack(_feature_format, self.type, self.bit_number, encoded_name)
        return result.ljust(_feature_format_size, b'\x00')

    def __repr__(self):
        return f'<{self.name}: 0x{self.type:x}:0x{self.bit_number:x}>'


_features: dict[str, type[_Feature]] = {}
_V = TypeVar('_V', bound=type[_Feature])


def _register_feature(cls: _V) -> _V:
    try:
        cls_name = cls.name
    except AttributeError:
        raise RuntimeError(
            f"Class {cls} must have integer attribute 'name' set to an appropriate string value")
    _features[cls_name] = cls
    return cls


@_register_feature
class _DirtyBit(_Feature):

    name = 'dirty bit'
    type = 0x0
    bit_number = 0x0


@_register_feature
class _CorruptBit(_Feature):

    name = 'corrupt bit'
    type = 0x0
    bit_number = 0x1


@_register_feature
class _ExternalDataFile(_Feature):

    name = 'external data file'
    type = 0x0
    bit_number = 0x2


@_register_feature
class _CompressionType(_Feature):

    name = 'compression type'
    type = 0x0
    bit_number = 0x3


@_register_feature
class _ExtendedL2Features(_Feature):

    name = 'extended L2 entries'
    type = 0x0
    bit_number = 0x4


@_register_feature
class _LazyRefcounts(_Feature):

    name = 'lazy refcounts'
    type = 0x1
    bit_number = 0x0


@_register_feature
class _Bitmaps(_Feature):

    name = 'bitmaps'
    type = 0x2
    bit_number = 0x0


@_register_feature
class _RawExternalData(_Feature):

    name = 'raw external data'
    type = 0x2
    bit_number = 0x1


@_register_extension
class _FeatureTable(_Extension):

    type = 0x6803f857

    def __init__(self, features: Sequence[_Feature]):
        self._features = list(features)
        super().__init__()

    def add(self, feature: _Feature):
        self._features.append(feature)

    def _get_raw(self):
        return b''.join(feature.as_bytes() for feature in self._features)

    @classmethod
    def from_raw(cls, data: bytes):
        features = []
        for _, _, name_raw in struct.iter_unpack(_feature_format, data):
            name = name_raw.rstrip(b'\x00').decode('utf-8')
            feature_class = _features.get(name)
            if feature_class is None:
                raise RuntimeError(f"Unknown feature {name!r}")
            features.append(feature_class())
        return cls(features)

    def __repr__(self):
        features = ', '.join(str(feature) for feature in self._features)
        return f'<Features: [{features}>]'


@_register_extension
class _BitmapsExtension(_Extension):

    type = 0x23852875

    def __init__(self, data: bytes):
        self._data = data

    def _get_raw(self):
        return self._data

    @classmethod
    def from_raw(cls, data: bytes):
        return cls(data)

    def __repr__(self):
        return f'<Bitmaps: {self._data!r}>'


@_register_extension
class _DiskEncryption(_Extension):

    type = 0x0537be77

    def __init__(self, data: bytes):
        self._data = data

    def _get_raw(self):
        return self._data

    @classmethod
    def from_raw(cls, data: bytes):
        return cls(data)

    def __repr__(self):
        return f'<DiskEncryption: {self._data!r}>'


@_register_extension
class _ExternalFile(_Extension):

    type = 0x44415441

    def __init__(self, file_name: str):
        self._file_name = file_name

    def _get_raw(self):
        return self._file_name.encode('utf-8')

    @classmethod
    def from_raw(cls, data: bytes):
        return cls(data.rstrip().decode('utf-8'))

    def __repr__(self):
        return f'<ExternalFile: {self._file_name!r}>'
