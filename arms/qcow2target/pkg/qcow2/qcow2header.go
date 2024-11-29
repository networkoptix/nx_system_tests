// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package qcow2

import (
	"encoding/binary"
	"fmt"
	"io"
	"os"
	"qcow2target/pkg/common"
)

// QcowMagic QCOW magic constant that starts the header.
const QcowMagic uint32 = 0x5146_49fb

const maxBackingFileNameSize = 1023

const MinClusterBits = 9

// DefaultClusterBits Default to a cluster size of 2^DefaultClusterBits
const DefaultClusterBits uint32 = 16
const MaxClusterBits uint32 = 30

// L1TableMaxSize is 32MB due to QUEMU implementation
const L1TableMaxSize = 32 * 1024 * 1024
const ClusterAddressSize = 8

// DefaultRefcountOrder Only support 2 byte refcounts, 2^refcount_order bits.
const DefaultRefcountOrder uint32 = 4
const V3BareHeaderSize uint32 = 104

const EmptyHeaderExtensionAreaSize uint32 = 8

const (
	incompatibleFeaturesDirtyBit uint64 = 1 << iota
	incompatibleFeaturesCorruptBit
	incompatibleFeaturesExternalDataFileBit
	incompatibleFeaturesCompressionTypeBit
	incompatibleFeaturesExtendedL2EntriesBit
)

const compatibleFeaturesLazyRefcounts uint64 = 1

const (
	autoClearFeaturesBitmapsExtension uint64 = 1
	autoClearFeaturesRawExternalData  uint64 = 2
)

type ImageHeader struct {
	// magic bytes must be equal to "QFI\xfb"
	magic uint32
	// versionNumber must be either 2 or 3
	versionNumber        uint32
	backingFileOffset    uint64
	backingFileSize      uint32
	clusterBits          uint32
	virtualDiskSizeBytes uint64
	cryptMethod          uint32
	// l1Size - number of entries in active l1 table
	l1Size                uint32
	l1TableOffset         uint64
	refCountTableOffset   uint64
	refCountTableClusters uint32
	nbSnapshots           uint32
	snapshotOffset        uint64
	// QCOW2 Version 3 specific features
	incompatibleFeatures uint64
	compatibleFeatures   uint64
	autoClearFeatures    uint64
	refCountOrder        uint32
	Length               uint32
	compressionType      uint8
	// Additional field which not present in actual
	// struct but used in computation
	clusterSize        uint64
	imageCorrupt       bool
	imageRefCountDirty bool
	lazyRefcounts      bool
	backingFilePath    *string
	numClusters        uint32
	l2Size             uint32
	numL2Clusters      uint32
	l1Clusters         uint32
	// this value must be the same as refCountTableClusters
	refCountClustersNumberComputed uint32
}

func (header ImageHeader) diskSizeLimitForCluster() uint64 {
	return L1TableMaxSize * header.clusterSize * header.clusterSize / ClusterAddressSize / ClusterAddressSize
}

func (header ImageHeader) validateMagic() error {
	if header.magic != QcowMagic {
		return newErrInvalidMagic(header.magic)
	}
	return nil
}

func (header ImageHeader) validateVersionNumber() error {
	if header.versionNumber != 3 {
		return newErrInvalidVersion(header.versionNumber)
	}
	return nil
}

func (header ImageHeader) validateBackingFileSizeOffset() error {
	if header.backingFileOffset == 0 {
		if header.backingFileSize > 0 {
			return newErrBackingFileZeroOffsetNameLengthNotZero(header.backingFileSize)
		}
	}
	if header.backingFileSize == 0 {
		if header.backingFileOffset > 0 {
			return newErrBackingFileNameNonZeroOffsetZeroLength(header.backingFileOffset)
		}
	}
	if header.backingFileSize > maxBackingFileNameSize {
		return newErrBackingFileNameTooLong(header.backingFileSize)
	}
	return nil
}

func (header ImageHeader) validateClusterBits() error {
	if (header.clusterBits < MinClusterBits) || (header.clusterBits > MaxClusterBits) {
		return newErrInvalidClusterBits(header.clusterBits)
	}
	return nil
}

func (header ImageHeader) validateVirtualDiskSize() error {
	diskSizeLimit := header.diskSizeLimitForCluster()
	if header.virtualDiskSizeBytes > diskSizeLimit {
		return fmt.Errorf(
			"virtual disk size is %s, must be less than %s due to "+
				"L1 cache size limitation",
			formatDiskSize(header.virtualDiskSizeBytes),
			formatDiskSize(diskSizeLimit),
		)
	}
	return nil
}

func (header ImageHeader) validateCryptMethod() error {
	if header.cryptMethod != 0 {
		return newErrUnsupportedCryptMethod(header.cryptMethod)
	}
	return nil
}

func (header ImageHeader) validateL1TableSize() error {
	if header.l1Size > L1TableMaxSize {
		return newErrL1TableTooLarge(header.l1Size)
	}
	return nil
}

func (header ImageHeader) validateL1TableOffset() error {
	// todo check if not the actual file size
	if header.l1TableOffset > header.virtualDiskSizeBytes {
		return fmt.Errorf(
			"table offset %d is more than virtual file size %d",
			header.l1TableOffset,
			header.virtualDiskSizeBytes,
		)
	}
	return nil
}

func (header ImageHeader) validateRefCountTableClusters() error {
	if header.refCountTableClusters == 0 {
		return newErrNoReferenceCountTableClusters()
	}
	return nil
}
func (header ImageHeader) validateNbSnapshots() error {
	if header.nbSnapshots != 0 {
		return newErrSnapshotsUnsupported(header.nbSnapshots)
	}
	return nil
}

func (header *ImageHeader) validateIncompatibleFeatures() error {
	if (header.incompatibleFeatures & incompatibleFeaturesCorruptBit) != 0 {
		header.imageCorrupt = true
	}
	if (header.incompatibleFeatures & incompatibleFeaturesDirtyBit) != 0 {
		header.imageRefCountDirty = true
	}
	if (header.incompatibleFeatures & incompatibleFeaturesCompressionTypeBit) != 0 {
		return newErrCompressionNotSupported()
	}
	if (header.incompatibleFeatures & incompatibleFeaturesExternalDataFileBit) != 0 {
		return newErrExternalDataFileNotSupported()
	}
	if (header.incompatibleFeatures & incompatibleFeaturesExtendedL2EntriesBit) != 0 {
		return newErrExtendedL2EntriesNotSupported()
	}
	return nil
}

func (header ImageHeader) validateAutoClearFeatures() error {
	if (header.autoClearFeatures & autoClearFeaturesRawExternalData) != 0 {
		return newErrRawExternalDataNotSupported()
	}
	if (header.autoClearFeatures & autoClearFeaturesBitmapsExtension) != 0 {
		return newErrBitmapExtensionsNotSupported()
	}
	return nil
}

func (header ImageHeader) validateRefCountOrder() error {
	// refCountOrder implementation limit
	if header.refCountOrder != 4 {
		return newErrInvalidReferenceCountOrder(header.refCountOrder)
	}
	return nil
}

func (header ImageHeader) validateHeaderLength() error {
	if header.Length < V3BareHeaderSize {
		return newErrInvalidHeaderLength(header.Length)
	}
	return nil
}

func (header ImageHeader) checkOffsetsForClusterBoundaries() error {
	if err := offsetIsClusterBoundary(header.l1TableOffset, header.clusterSize); err != nil {
		return err
	}
	if err := offsetIsClusterBoundary(header.snapshotOffset, header.clusterSize); err != nil {
		return err
	}
	// refcount table must be a cluster boundary, and within the file's virtual or actual size.
	if err := offsetIsClusterBoundary(header.refCountTableOffset, header.clusterSize); err != nil {
		return err
	}
	return nil
}

func (header *ImageHeader) preComputeTableSizes() {
	// L2 blocks are always one cluster long
	// address is uint64, 8 bytes size
	header.numClusters = uint32(divRoundUp[uint64](header.virtualDiskSizeBytes, header.clusterSize))
	header.l2Size = uint32(header.clusterSize / 8)
	header.numL2Clusters = divRoundUp[uint32](header.numClusters, header.l2Size)
	header.l1Clusters = divRoundUp[uint32](header.numL2Clusters, uint32(header.clusterSize))
	header.refCountClustersNumberComputed = findRefcountTableClustersNumber(
		header.numClusters,
		header.numL2Clusters,
		header.l1Clusters,
		uint32(header.clusterSize))
}

func (header ImageHeader) refcountTableSizeSanityCheck() error {
	// Check that the given header doesn't have a suspiciously sized refcount table.
	// todo (svorobev) ported from crossvm qcow2, find a beter explanaition

	if header.refCountTableClusters > 2*header.refCountClustersNumberComputed {
		return fmt.Errorf(
			"too many clusters (%d) specified for reference count table",
			header.refCountTableClusters,
		)
	}
	if header.l1Clusters+header.refCountClustersNumberComputed > L1TableMaxSize {
		// Compare with L1 table max size as a max size for in-memory
		// ref count table (in other implementations the same value
		// was used for L1 table max size and refCount table limitations)
		return fmt.Errorf(
			"reference count table is too large (%d)",
			header.l1Clusters+header.refCountClustersNumberComputed,
		)
	}
	return nil
}

func (header ImageHeader) validateNumberOfL2Clusters() error {
	if header.numL2Clusters > L1TableMaxSize {
		return fmt.Errorf(
			"reference count table is too large (%d)",
			header.numL2Clusters,
		)
	}
	return nil
}

func (header ImageHeader) validate() error {
	if err := header.validateMagic(); err != nil {
		return err
	}
	if err := header.validateVersionNumber(); err != nil {
		return err
	}
	if err := header.validateBackingFileSizeOffset(); err != nil {
		return err
	}
	if err := header.validateClusterBits(); err != nil {
		return err
	}
	if err := header.validateVirtualDiskSize(); err != nil {
		return err
	}
	if err := header.validateCryptMethod(); err != nil {
		return err
	}
	if err := header.validateL1TableSize(); err != nil {
		return err
	}
	if err := header.validateL1TableOffset(); err != nil {
		return err
	}
	if err := header.validateRefCountTableClusters(); err != nil {
		return err
	}
	if err := header.validateNbSnapshots(); err != nil {
		return err
	}
	if err := header.validateIncompatibleFeatures(); err != nil {
		return err
	}
	if err := header.validateAutoClearFeatures(); err != nil {
		return err
	}
	if err := header.validateRefCountOrder(); err != nil {
		return err
	}
	if err := header.validateHeaderLength(); err != nil {
		return err
	}
	if err := header.checkOffsetsForClusterBoundaries(); err != nil {
		return err
	}
	if err := header.validateNumberOfL2Clusters(); err != nil {
		return err
	}
	if err := header.refcountTableSizeSanityCheck(); err != nil {
		return err
	}
	return nil
}

func (header ImageHeader) toByte() []byte {
	bytes := make([]byte, 0, 72)
	bytes = append(bytes, uint32ToByte(header.magic)...)
	bytes = append(bytes, uint32ToByte(header.versionNumber)...)
	bytes = append(bytes, uint64ToByte(header.backingFileOffset)...)
	bytes = append(bytes, uint32ToByte(header.backingFileSize)...)
	bytes = append(bytes, uint32ToByte(header.clusterBits)...)
	bytes = append(bytes, uint64ToByte(header.virtualDiskSizeBytes)...)
	bytes = append(bytes, uint32ToByte(header.cryptMethod)...)
	bytes = append(bytes, uint32ToByte(header.l1Size)...)
	bytes = append(bytes, uint64ToByte(header.l1TableOffset)...)
	bytes = append(bytes, uint64ToByte(header.refCountTableOffset)...)
	bytes = append(bytes, uint32ToByte(header.refCountTableClusters)...)
	bytes = append(bytes, uint32ToByte(header.nbSnapshots)...)
	bytes = append(bytes, uint64ToByte(header.snapshotOffset)...)
	bytes = append(bytes, uint64ToByte(header.incompatibleFeatures)...)
	bytes = append(bytes, uint64ToByte(header.compatibleFeatures)...)
	bytes = append(bytes, uint64ToByte(header.autoClearFeatures)...)
	bytes = append(bytes, uint32ToByte(header.refCountOrder)...)
	bytes = append(bytes, uint32ToByte(header.Length)...)
	if header.Length == 104 {
		return bytes
	}
	compressionWithPadding := [8]byte{header.compressionType, 0, 0, 0, 0, 0, 0, 0}
	bytes = append(bytes, compressionWithPadding[:]...)
	return bytes
}

func imageHeaderFromFile(file io.ReadSeeker) (*ImageHeader, error) {
	err := error(nil)
	_, err = file.Seek(0, 0)
	if err != nil {
		return nil, err
	}
	magic := uint32(0)
	if err = binary.Read(file, binary.BigEndian, &magic); err != nil {
		return nil, err
	}
	versionNumber := uint32(0)
	if err = binary.Read(file, binary.BigEndian, &versionNumber); err != nil {
		return nil, err
	}
	backingFileOffset := uint64(0)
	if err = binary.Read(file, binary.BigEndian, &backingFileOffset); err != nil {
		return nil, err
	}
	backingFileSize := uint32(0)
	if err = binary.Read(file, binary.BigEndian, &backingFileSize); err != nil {
		return nil, err
	}
	clusterBits := uint32(0)
	if err = binary.Read(file, binary.BigEndian, &clusterBits); err != nil {
		return nil, err
	}
	virtualDiskSizeBytes := uint64(0)
	if err = binary.Read(file, binary.BigEndian, &virtualDiskSizeBytes); err != nil {
		return nil, err
	}
	cryptMethod := uint32(0)
	if err = binary.Read(file, binary.BigEndian, &cryptMethod); err != nil {
		return nil, err
	}
	l1Size := uint32(0)
	if err = binary.Read(file, binary.BigEndian, &l1Size); err != nil {
		return nil, err
	}
	l1TableOffset := uint64(0)
	if err = binary.Read(file, binary.BigEndian, &l1TableOffset); err != nil {
		return nil, err
	}
	refCountTableOffset := uint64(0)
	if err = binary.Read(file, binary.BigEndian, &refCountTableOffset); err != nil {
		return nil, err
	}
	refCountTableClusters := uint32(0)
	if err = binary.Read(file, binary.BigEndian, &refCountTableClusters); err != nil {
		return nil, err
	}
	nbSnapshots := uint32(0)
	if err = binary.Read(file, binary.BigEndian, &nbSnapshots); err != nil {
		return nil, err
	}
	snapshotOffset := uint64(0)
	if err = binary.Read(file, binary.BigEndian, &snapshotOffset); err != nil {
		return nil, err
	}
	incompatibleFeatures := uint64(0)
	if err = binary.Read(file, binary.BigEndian, &incompatibleFeatures); err != nil {
		return nil, err
	}
	compatibleFeatures := uint64(0)
	if err = binary.Read(file, binary.BigEndian, &compatibleFeatures); err != nil {
		return nil, err
	}
	autoClearFeatures := uint64(0)
	if err = binary.Read(file, binary.BigEndian, &autoClearFeatures); err != nil {
		return nil, err
	}
	refCountOrder := uint32(0)
	if err = binary.Read(file, binary.BigEndian, &refCountOrder); err != nil {
		return nil, err
	}
	headerLength := uint32(0)
	if err = binary.Read(file, binary.BigEndian, &headerLength); err != nil {
		return nil, err
	}
	compressionType := uint8(0)
	if headerLength > V3BareHeaderSize {
		if err = binary.Read(file, binary.BigEndian, &compressionType); err != nil {
			return nil, err
		}
	}
	var backingFilePath *string
	if backingFileOffset != 0 {
		if backingFileSize != 0 {
			backingFilePathBytes := make([]byte, backingFileSize)
			_, err = file.Seek(int64(backingFileOffset), 0)
			if err != nil {
				return nil, fmt.Errorf(
					"while seeking backing file offset, an error occured %s",
					err,
				)
			}
			_, err = io.ReadFull(file, backingFilePathBytes)
			if err != nil {
				return nil, fmt.Errorf(
					"while reading backing file path, an error occured %s",
					err,
				)
			}
			backingFilePath = new(string)
			*backingFilePath = string(backingFilePathBytes)
		}
	}
	header := ImageHeader{
		magic:                 magic,
		versionNumber:         versionNumber,
		backingFileOffset:     backingFileOffset,
		backingFileSize:       backingFileSize,
		clusterBits:           clusterBits,
		virtualDiskSizeBytes:  virtualDiskSizeBytes,
		cryptMethod:           cryptMethod,
		l1Size:                l1Size,
		l1TableOffset:         l1TableOffset,
		refCountTableOffset:   refCountTableOffset,
		refCountTableClusters: refCountTableClusters,
		nbSnapshots:           nbSnapshots,
		snapshotOffset:        snapshotOffset,
		incompatibleFeatures:  incompatibleFeatures,
		compatibleFeatures:    compatibleFeatures,
		autoClearFeatures:     autoClearFeatures,
		refCountOrder:         refCountOrder,
		Length:                headerLength,
		compressionType:       compressionType,
		clusterSize:           getClusterSize(clusterBits),
		backingFilePath:       backingFilePath,
	}
	header.preComputeTableSizes()
	err = header.validate()
	if err != nil {
		return nil, err
	}
	return &header, nil
}

func findRefcountTableClustersNumber(numClusters, numL2Clusters, l1Clusters, clusterSize uint32) uint32 {
	_maxRefCountClusters := maxRefCountClusters(numClusters, numL2Clusters, l1Clusters, clusterSize)
	uint64Size := uint32(8)
	return divRoundUp[uint32](_maxRefCountClusters*uint64Size, clusterSize)
}

func maxRefCountClusters(numClusters uint32, numL2Clusters uint32, l1Clusters uint32, clusterSize uint32) uint32 {
	// Each ref count is 2 bytes by default
	refcountBytes := uint32(1<<DefaultRefcountOrder) / 8
	// Refcount table is two level,
	// first is refcount table which is continuous and
	// contains offset for all refcount clusters
	headerClusters := 1
	numberOfClusters := numClusters + numL2Clusters + l1Clusters + uint32(headerClusters)
	refCountClustersForData := divRoundUp[uint32](numberOfClusters*refcountBytes, clusterSize)
	refCountClustersForRefCounts := divRoundUp[uint32](refCountClustersForData*refcountBytes, clusterSize)
	maxRefCountClusters := refCountClustersForData + refCountClustersForRefCounts
	return maxRefCountClusters
}

func createHeaderForSizeAndPath(size uint64, backingFilePath *string) (*ImageHeader, error) {
	clusterSize := getClusterSize(DefaultClusterBits)
	l2Size := uint32(clusterSize / 8)
	numClusters := uint32(divRoundUp[uint64](size, clusterSize))
	numL2Clusters := divRoundUp[uint32](numClusters, l2Size)
	l1Clusters := divRoundUp[uint32](numL2Clusters, uint32(clusterSize))
	backingFileSize := uint32(0)
	backingFileOffset := uint64(0)
	maxLength := uint32(clusterSize) - V3BareHeaderSize - EmptyHeaderExtensionAreaSize
	if backingFilePath != nil {
		backingFileOffset = uint64(V3BareHeaderSize + EmptyHeaderExtensionAreaSize)
		backingFileSize = uint32(len(*backingFilePath))

		if backingFileSize > maxLength { // min of 1-23 and max length
			return nil, fmt.Errorf(
				"backing file path of size %d is too long, expected values < %d",
				backingFileSize,
				maxLength,
			)
		}
	}
	header := ImageHeader{
		magic:                QcowMagic,
		versionNumber:        3,
		backingFileOffset:    backingFileOffset,
		backingFileSize:      backingFileSize,
		clusterBits:          DefaultClusterBits,
		virtualDiskSizeBytes: size,
		cryptMethod:          0,
		l1Size:               numL2Clusters,
		l1TableOffset:        clusterSize,
		refCountTableOffset:  clusterSize * uint64(l1Clusters+1),
		refCountTableClusters: findRefcountTableClustersNumber(
			numClusters,
			numL2Clusters,
			l1Clusters,
			uint32(clusterSize)),
		nbSnapshots:          0,
		snapshotOffset:       0,
		incompatibleFeatures: 0,
		compatibleFeatures:   0,
		autoClearFeatures:    0,
		refCountOrder:        DefaultRefcountOrder,
		Length:               V3BareHeaderSize,
		compressionType:      0,
		backingFilePath:      backingFilePath,
		clusterSize:          clusterSize,
	}
	diskSizeLimit := header.diskSizeLimitForCluster()
	if size > diskSizeLimit {
		return nil, fmt.Errorf(
			"virtual disk size is %s, must be less than %s due to "+
				"L1 cache size limitation",
			formatDiskSize(size),
			formatDiskSize(diskSizeLimit),
		)
	}
	if (header.compatibleFeatures & compatibleFeaturesLazyRefcounts) != 0 {
		header.lazyRefcounts = true
	}
	header.preComputeTableSizes()
	return &header, nil
}

func (header ImageHeader) writeToFile(file *os.File) error {
	headerBytes := header.toByte()
	_, err := file.Seek(0, 0)
	if err != nil {
		return err
	}
	_, err = file.Write(headerBytes)
	if err != nil {
		return common.RaiseFrom(err, newErrHeaderWrite())
	}
	_, err = file.Write(
		[]byte{
			0x00, 0x00, 0x00, 0x00, // end of header extension area
			0x00, 0x00, 0x00, 0x00, // length of header extension = 0
		},
	)
	if err != nil {
		return common.RaiseFrom(err, newErrHeaderWrite())
	}
	if header.backingFilePath != nil {
		_, err = file.Write([]byte(*header.backingFilePath))
		if err != nil {
			return common.RaiseFrom(err, newErrHeaderWrite())
		}
	}
	// Set file length by seeking zero to the last byte
	// Zeros out L1 and refcount table clusters
	refCountBlocksSize := uint64(header.refCountTableClusters) * header.clusterSize
	_, err = file.Seek(int64(refCountBlocksSize+header.refCountTableOffset-2), 0)
	if err != nil {
		return common.RaiseFrom(err, newErrHeaderWrite())
	}
	_, err = file.Write([]byte{0x00})
	if err != nil {
		return common.RaiseFrom(err, newErrHeaderWrite())
	}
	return nil
}
