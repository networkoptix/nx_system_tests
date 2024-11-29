// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package qcow2

import (
	"encoding/binary"
	"fmt"
	"math/bits"
	"os"
)

// QcowRawFile A qcow file. Allows reading/writing clusters and appending clusters.
type QcowRawFile struct {
	file        *os.File
	clusterSize uint64
	clusterMask uint64
	readOnly    bool
}

// Creates a `QcowRawFile` from the given `File`, `None` is returned if `cluster_size` is not
// a power of two.
func qcowRawFileFromFile(file *os.File, clusterSize uint64, readOnly bool) (*QcowRawFile, error) {
	if bits.OnesCount(uint(clusterSize)) != 1 {
		return nil, fmt.Errorf("invalid cluster size %d, must be power of two", clusterSize)
	}
	return &QcowRawFile{
		file:        file,
		clusterSize: clusterSize,
		clusterMask: clusterSize - 1,
		readOnly:    readOnly,
	}, nil
}

// read only methods

func (rawFile QcowRawFile) isReadOnly() bool {
	return rawFile.readOnly
}

func (rawFile QcowRawFile) size() (uint64, error) {
	stat, err := rawFile.file.Stat()
	if err != nil {
		return 0, err
	}
	return uint64(stat.Size()), nil
}

func (rawFile QcowRawFile) close() error {
	return rawFile.file.Close()
}

func (rawFile QcowRawFile) ReadAt(bytes []byte, offset int64) error {
	_, err := rawFile.file.ReadAt(bytes, offset)
	return err
}

func (rawFile QcowRawFile) readUint16At(offset uint64) (uint16, error) {
	return readUint16At(rawFile.file, offset)
}

func (rawFile QcowRawFile) readUint64At(offset uint64) (uint64, error) {
	return readUint64At(rawFile.file, offset)
}

// Reads `count` 64 bit offsets and returns them as an uint64 array.
// `mask` optionally ands out some of the bits on the file.
func (rawFile QcowRawFile) readPointerTable(
	offset uint64,
	count uint64,
	mask uint64,
) ([]uint64, error) {
	table := make([]uint64, count)
	_, err := rawFile.file.Seek(int64(offset), 0)
	if err != nil {
		return nil, err
	}
	if mask == 0 { // to avoid using optional, replace empty mask with 0
		// since mask can't be zero normally
		mask = ^uint64(0)
	}
	for index := range table {
		value := uint64(0)
		if err = binary.Read(rawFile.file, binary.BigEndian, &value); err != nil {
			return nil, err
		}
		table[index] = value & mask
	}
	return table, nil
}

// Read cluster containing pointers to other clusters
func (rawFile QcowRawFile) readPointerCluster(offset uint64, mask uint64) ([]uint64, error) {
	count := rawFile.clusterSize / uint64(8)
	value, err := rawFile.readPointerTable(offset, count, mask)
	return value, err
}

func (rawFile QcowRawFile) readRefCountBlock(offset uint64) ([]uint16, error) {
	uint16Size := uint64(2) // todo here reference count bits are used
	count := rawFile.clusterSize / uint16Size
	table := make([]uint16, count)
	_, err := rawFile.file.Seek(int64(offset), 0)
	if err != nil {
		return nil, err
	}
	for index := range table {
		value := uint16(0)
		if err := binary.Read(rawFile.file, binary.BigEndian, &value); err != nil {
			return nil, err
		}
		table[index] = value
	}
	return table, nil
}

func (rawFile QcowRawFile) clusterOffset(address uint64) uint64 {
	return address & rawFile.clusterMask
}

// Limits the range so that it doesn't overflow the end of a cluster.
func (rawFile QcowRawFile) limitRangeCluster(address uint64, count uint64) uint64 {
	offset := rawFile.clusterOffset(address)
	limit := rawFile.clusterSize - offset
	if count < limit {
		return count
	}
	return limit
}

// write methods need to check for read only
func (rawFile QcowRawFile) sync() error {
	if rawFile.readOnly {
		return newErrAttemptToSyncReadOnlyFile()
	}
	return rawFile.file.Sync()
}

func (rawFile QcowRawFile) WriteAt(bytes []byte, offset int64) error {
	if rawFile.readOnly {
		return newErrWriteAttemptToReadOnlyDisk(uint64(offset), uint64(len(bytes)))
	}
	_, err := rawFile.file.WriteAt(bytes, offset)
	return err
}

func (rawFile QcowRawFile) writeUint64At(value, offset uint64) error {
	if rawFile.readOnly {
		return newErrWriteAttemptToReadOnlyDisk(offset, 8)
	}
	return writeUint64At(rawFile.file, value, offset)
}

func (rawFile QcowRawFile) writeUint16At(value uint16, offset uint64) error {
	if rawFile.readOnly {
		return newErrWriteAttemptToReadOnlyDisk(offset, 2)
	}
	return writeUint16At(rawFile.file, value, offset)
}

func (rawFile QcowRawFile) writeHeader(header ImageHeader) error {
	if rawFile.readOnly {
		return newErrWriteAttemptToReadOnlyDisk(0, uint64(header.Length))
	}
	_, err := rawFile.file.Seek(0, 0)
	if err != nil {
		return err
	}
	return header.writeToFile(rawFile.file)
}

// Writes `table` of uint64 pointers to `offset` in the file.
// `non_zero_flags` will be ORed with all non-zero values in `table`.
// writing.
func (rawFile QcowRawFile) writePointerTable(
	offset uint64,
	table []uint64,
	nonZeroFlags uint64,
) error {
	if rawFile.readOnly {
		return newErrWriteAttemptToReadOnlyDisk(offset, uint64(len(table)*8))
	}
	_, err := rawFile.file.Seek(int64(offset), 0)
	if err != nil {
		return err
	}
	toWrite := make([]byte, 0, len(table))
	for _, value := range table {
		if value == 0 {
			toWrite = append(toWrite, uint64ToByte(value)...)
		} else {
			toWrite = append(toWrite, uint64ToByte(value|nonZeroFlags)...)
		}
	}
	_, err = rawFile.file.Write(toWrite)
	if err != nil {
		return err
	}
	return nil
}

func (rawFile QcowRawFile) writeRefcountBlock(offset uint64, table []uint16) error {
	if rawFile.readOnly {
		return newErrWriteAttemptToReadOnlyDisk(offset, uint64(len(table)*2))
	}
	_, err := rawFile.file.Seek(int64(offset), 0)
	if err != nil {
		return err
	}
	toWrite := make([]byte, 0, len(table))
	for _, value := range table {
		toWrite = append(toWrite, uint16ToByte(value)...)
	}
	_, err = rawFile.file.Write(toWrite)
	if err != nil {
		return err
	}
	return nil
}

func (rawFile QcowRawFile) allocateClusterAtFileEnd(maxValidClusterOffset uint64) (uint64, error) {
	if rawFile.readOnly {
		return 0, newErrAttemptToTruncateReadOnlyFile()
	}
	fileEnd, err := rawFile.file.Seek(0, 2)
	if err != nil {
		return 0, err
	}
	newClusterAddress := (uint64(fileEnd) + rawFile.clusterSize - uint64(1)) & (^rawFile.clusterMask)
	if newClusterAddress > maxValidClusterOffset {
		return 0, fmt.Errorf("wrong new cluster address")
	}
	err = rawFile.file.Truncate(int64(newClusterAddress + rawFile.clusterSize))
	if err != nil {
		return 0, err
	}
	return newClusterAddress, nil
}

func (rawFile QcowRawFile) zeroCluster(address uint64) error {

	_, err := rawFile.file.Seek(int64(address), 0)
	if err != nil {
		return err
	}
	zeroClusters := make([]byte, rawFile.clusterSize)
	_, err = rawFile.file.Write(zeroClusters)
	if err != nil {
		return err
	}
	return nil
}

func (rawFile QcowRawFile) writeCluster(address uint64, initialData []byte) error {
	if rawFile.readOnly {
		return newErrWriteAttemptToReadOnlyDisk(address, uint64(len(initialData)))
	}
	// crossvm uses write_volatile_at,
	// which is actually pwrite64 in a loop
	// (in order ot handle signal interrupt),
	// using also an unsafe pointer cast.
	// See: https://google.github.io/crosvm/doc/src/base/sys/unix/file_traits.rs.html
	// EINTR is being handled in FD.PWrite in golang which
	// is called in WriteAt API call.
	if uint64(len(initialData)) < rawFile.clusterSize {
		return fmt.Errorf("initital data is too small")
	}
	_, err := rawFile.file.WriteAt(initialData, int64(address))
	if err != nil {
		return err
	}
	return nil
}
