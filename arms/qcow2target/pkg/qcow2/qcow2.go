// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package qcow2

import (
	"bytes"
	"encoding/binary"
	"errors"
	"fmt"
	"os"
	"path/filepath"
)

// L1TableOffsetMask bits 0-8 and 56-63 are reserved.
const L1TableOffsetMask uint64 = 0x00ff_ffff_ffff_fe00
const L2TableOffsetMask uint64 = 0x00ff_ffff_ffff_fe00

// CompressedFlag Flags
const CompressedFlag uint64 = 1 << 62
const ClusterUsedFlag uint64 = 1 << 63

const backingFileMaxNestingDepth = 10

type referenceCountToSet struct {
	address uint64
	value   uint16
}

type ImageFile struct {
	fullImagePath   string
	rawFile         QcowRawFile
	header          ImageHeader
	pointerTable    pointerTableCache
	referenceCounts ReferenceCountTable
	unrefClusters   []uint64
	availClusters   []uint64
	backingFile     *ImageFile
	closed          bool
	readOnly        bool
}

type ImageFactory struct {
	useCache                     bool
	pointerTableCacheSize        int
	referenceCountTableCacheSize int
}

func CachedImageFactory() *ImageFactory {
	return &ImageFactory{
		useCache:                     true,
		pointerTableCacheSize:        100,
		referenceCountTableCacheSize: 50,
	}
}

func NoCacheImageFactory() *ImageFactory {
	return &ImageFactory{
		useCache:                     false,
		pointerTableCacheSize:        0,
		referenceCountTableCacheSize: 0,
	}
}

func NewImageFactory(useCache bool) *ImageFactory {
	if useCache {
		return CachedImageFactory()
	} else {
		return NoCacheImageFactory()
	}
}

func ResolveBackingFilePath(backingFilePath, childDiskPath string) string {
	// childDiskPath must be absolute
	// otherwise we won't be able to find backingFilePath
	// if backingFilePath is relative
	if filepath.IsAbs(backingFilePath) {
		return backingFilePath
	} else {
		childDir := filepath.Dir(childDiskPath)
		return filepath.Join(childDir, backingFilePath)
	}
}

func resolveBackingFileImage(backingFilePath, childDiskPath string) (file *os.File, resolvedBackingPath string, err error) {
	resolvedBackingPath = ResolveBackingFilePath(backingFilePath, childDiskPath)
	backingFileExists, err := PathExists(resolvedBackingPath)
	if err != nil {
		return nil, resolvedBackingPath, err
	}
	if !backingFileExists {
		return nil, resolvedBackingPath, newErrParentDiskDoesNotExist(backingFilePath, childDiskPath)
	}
	file, err = os.Open(resolvedBackingPath)
	if err != nil {
		return nil, resolvedBackingPath, err
	}
	return
}

func (factory ImageFactory) getBackingFileImage(
	backingFilePath, childDiskPath string,
	recursionDepth uint32,
) (*ImageFile, error) {
	if recursionDepth == 0 {
		return nil, newErrRecursionDepthExceeded(backingFileMaxNestingDepth)
	}
	backingFile, resolvedBackingFilePath, err := resolveBackingFileImage(backingFilePath, childDiskPath)
	if err != nil {
		return nil, err
	}
	return factory.imageFromFile(resolvedBackingFilePath, backingFile, recursionDepth, true)
}

func (factory ImageFactory) resolveImagePath(imagePath string) (string, error) {
	if !filepath.IsAbs(imagePath) {
		return "", newNonAbsolutePathError(imagePath)
	}
	directory := filepath.Dir(imagePath)
	dirExists, err := PathExists(directory)
	if err != nil {
		return "", err
	}
	if !dirExists {
		return "", newErrDiskDirectoryDoesNotExist(directory)
	}
	return imagePath, nil
}

func (factory ImageFactory) imageFromFile(
	filePath string,
	file *os.File,
	recursionDepth uint32,
	readOnly bool,
) (*ImageFile, error) {
	header, err := imageHeaderFromFile(file)
	if err != nil {
		return nil, err
	}
	rawFile, err := qcowRawFileFromFile(file, header.clusterSize, readOnly)
	if err != nil {
		return nil, err
	}
	var backingFileImage *ImageFile
	if header.backingFilePath != nil {
		backingFileImage, err = factory.getBackingFileImage(
			*header.backingFilePath,
			filePath,
			recursionDepth-1)
		if err != nil {
			return nil, err
		}
	}
	referenceCountRebuildRequired := true
	_, err = file.Seek(int64(header.refCountTableOffset), 0)
	if err != nil {
		return nil, err
	}
	firstReferenceBlockAddress := uint64(0)
	if err = binary.Read(file, binary.BigEndian, &firstReferenceBlockAddress); err != nil {
		return nil, err
	}
	if firstReferenceBlockAddress != uint64(0) {
		_, err = file.Seek(int64(firstReferenceBlockAddress), 0)
		if err != nil {
			return nil, err
		}
		firstClusterRefcount := uint16(0)
		if err := binary.Read(file, binary.BigEndian, &firstClusterRefcount); err != nil {
			return nil, err
		}
		if firstClusterRefcount != 0 {
			referenceCountRebuildRequired = false
		}
	}
	if header.lazyRefcounts {
		referenceCountRebuildRequired = true
	}
	if readOnly && referenceCountRebuildRequired {
		return nil, newErrReadOnlyImageBrokenReferenceCounts()
	}
	if referenceCountRebuildRequired {
		err = rebuildReferenceCounts(
			*rawFile,
			*header,
		)
		if err != nil {
			return nil, err
		}
	}
	refcountBytes := ((uint64(1) << header.refCountOrder) + uint64(7)) / uint64(8)
	refcountBlockEntries := header.clusterSize / refcountBytes
	pointerCache, err := newPointerTable(*header, *rawFile, factory.useCache, factory.pointerTableCacheSize)
	if err != nil {
		return nil, err
	}
	referenceCounts, err := newReferenceCount(
		*rawFile,
		header.refCountTableOffset,
		uint64(
			maxRefCountClusters(
				header.numClusters,
				header.numL2Clusters,
				header.l1Clusters,
				uint32(header.clusterSize),
			),
		),
		refcountBlockEntries,
		header.clusterSize,
		factory.useCache,
		factory.referenceCountTableCacheSize,
	)
	if err != nil {
		return nil, err
	}
	unrefClusters := make([]uint64, 0, 100)
	availClusters := make([]uint64, 0, 100)
	image := ImageFile{
		fullImagePath:   filePath,
		rawFile:         *rawFile,
		header:          *header,
		backingFile:     backingFileImage,
		referenceCounts: referenceCounts,
		pointerTable:    pointerCache,
		unrefClusters:   unrefClusters,
		availClusters:   availClusters,
		closed:          false,
		readOnly:        readOnly,
	}
	err = checkAddUint64Boundaries(
		header.l1TableOffset,
		image.l1AddressOffset(image.header.virtualDiskSizeBytes),
	)
	if err != nil {
		return nil, err
	}
	err = checkAddUint64Boundaries(
		image.header.refCountTableOffset,
		uint64(image.header.refCountTableClusters)*image.header.clusterSize,
	)
	if err != nil {
		return nil, err
	}
	err = image.findAvailableClusters()
	if err != nil {
		return nil, err
	}
	return &image, nil
}

func (factory ImageFactory) CreateImage(filePath string, virtualSize uint64) (*ImageFile, error) {
	filePath, err := factory.resolveImagePath(filePath)
	if err != nil {
		return nil, err
	}
	pathExists, err := PathExists(filePath)
	if err != nil {
		return nil, err
	}
	if pathExists {
		return nil, fmt.Errorf("path %s already exists", filePath)
	}
	header, err := createHeaderForSizeAndPath(virtualSize, nil)
	if err != nil {
		return nil, err
	}
	imageFile, err := factory.createImageFromHeader(filePath, *header, 1)
	return imageFile, err
}

func (factory ImageFactory) CreateImageFromBacking(
	filePath string,
	backingFileName string,
) (*ImageFile, error) {
	filePath, err := factory.resolveImagePath(filePath)
	if err != nil {
		return nil, err
	}
	pathExists, err := PathExists(filePath)
	if err != nil {
		return nil, err
	}
	if pathExists {
		return nil, fmt.Errorf("path %s already exists", filePath)
	}
	backingFileImage, err := factory.getBackingFileImage(backingFileName, filePath, backingFileMaxNestingDepth-1)
	if err != nil {
		return nil, err
	}
	header, err := createHeaderForSizeAndPath(
		backingFileImage.header.virtualDiskSizeBytes,
		&backingFileName,
	)
	if err != nil {
		return nil, err
	}
	imageFile, err := factory.createImageFromHeader(filePath, *header, backingFileMaxNestingDepth)
	return imageFile, err
}

func (factory ImageFactory) createImageFromHeader(
	filePath string,
	header ImageHeader,
	maxNestingDepth uint32,
) (*ImageFile, error) {
	file, err := os.Create(filePath)
	if err != nil {
		return nil, err
	}
	_, err = file.Seek(0, 0)
	if err != nil {
		return nil, err
	}
	err = header.writeToFile(file)
	if err != nil {
		return nil, err
	}
	qcowImage, err := factory.imageFromFile(filePath, file, maxNestingDepth, false)
	if err != nil {
		return nil, err
	}
	endClusterAddress := header.refCountTableOffset +
		uint64(header.refCountTableClusters)*header.clusterSize
	for clusterAddress := uint64(0); clusterAddress < endClusterAddress; clusterAddress += header.clusterSize {
		unreferencedClusters, err := qcowImage.setClusterRefcount(clusterAddress, 1)
		if err != nil {
			return nil, err
		}
		qcowImage.unrefClusters = append(qcowImage.unrefClusters, unreferencedClusters...)
	}
	return qcowImage, nil
}

func (factory ImageFactory) OpenImage(filePath string, recursionDepth uint32) (*ImageFile, error) {
	filePath, err := factory.resolveImagePath(filePath)
	if err != nil {
		return nil, err
	}
	file, err := os.OpenFile(filePath, os.O_RDWR, 0755)
	if err != nil {
		return nil, err
	}
	return factory.imageFromFile(filePath, file, recursionDepth, false)
}

func (imageFile *ImageFile) findAvailableClusters() error {
	size, err := imageFile.rawFile.size()
	if err != nil {
		return err
	}
	for i := uint64(0); i < size; i += imageFile.header.clusterSize {
		refcount, err := imageFile.referenceCounts.getClusterRefcount(i)
		if err != nil {
			return err
		}
		if refcount == 0 {
			imageFile.availClusters = append(imageFile.availClusters, i)
		}
	}
	return nil
}

// Limits the range so that it doesn't exceed the virtual size of the file.
func (imageFile ImageFile) limitRangeFile(address uint64, count uint64) uint64 {
	err := checkAddUint64Boundaries(address, count)
	if err != nil {
		return 0
	}
	if address > imageFile.header.virtualDiskSizeBytes {
		return 0
	}
	remainingOffset := imageFile.header.virtualDiskSizeBytes - address
	if count < remainingOffset {
		return count
	}
	return remainingOffset
}

// Gets the offset of `address` in the L1 table.
func (imageFile ImageFile) l1AddressOffset(address uint64) uint64 {
	l1Index := l1TableIndex(imageFile.header, address)
	return l1Index * 8
}

func (imageFile *ImageFile) setClusterRefcount(
	address uint64,
	referenceCount uint16,
) ([]uint64, error) {
	addedClusters := make([]uint64, 0)
	unreferencedClusters := make([]uint64, 0)
	referenceCountsAreSet := false
	var _newCluster *newCluster
	for !referenceCountsAreSet {
		droppedCluster, hasValue, err := imageFile.referenceCounts.setClusterRefcount(
			address,
			referenceCount,
			_newCluster,
		)
		if err != nil {
			if _, ok := err.(*ErrNeedNewCluster); ok {
				address, _err := imageFile.getNewCluster(nil)
				if _err != nil {
					return nil, _err
				}
				addedClusters = append(addedClusters, address)
				_newCluster = &newCluster{
					clusterAddress: address,
					referenceCountBlock: newVectorCache[uint16](
						imageFile.referenceCounts.referenceCountsPerBlock(),
					),
				}
				continue
			}
			if needReadClusterErr, ok := err.(*ErrNeedReadCluster); ok {
				block, err := imageFile.rawFile.readRefCountBlock(needReadClusterErr.address)
				if err != nil {
					return nil, err
				}
				_newCluster = &newCluster{
					clusterAddress:      needReadClusterErr.address,
					referenceCountBlock: vectorCacheFromArray[uint16](block),
				}
				continue
			}
			return nil, err
		} else if !hasValue {
			referenceCountsAreSet = true
		} else {
			unreferencedClusters = append(unreferencedClusters, droppedCluster)
			referenceCountsAreSet = true
		}
	}
	for _, address := range addedClusters {
		_, err := imageFile.setClusterRefcount(address, 1)
		if err != nil {
			return nil, err
		}
	}
	return unreferencedClusters, nil
}

func (imageFile *ImageFile) getNewCluster(initialData []uint8) (uint64, error) {
	if length := len(imageFile.availClusters); length > 0 {
		newClusterAddress := imageFile.availClusters[length-1]
		imageFile.availClusters = imageFile.availClusters[:length-1]
		if initialData != nil {
			err := imageFile.rawFile.writeCluster(newClusterAddress, initialData)
			if err != nil {
				return 0, err
			}
		} else {
			err := imageFile.rawFile.zeroCluster(newClusterAddress)
			if err != nil {
				return 0, err
			}
		}
		return newClusterAddress, nil
	}
	maxValidClusterOffset := imageFile.referenceCounts.maxValidClusterOffset()
	newClusterAddress, err := imageFile.rawFile.allocateClusterAtFileEnd(maxValidClusterOffset)
	if err != nil {
		return 0, err
	}
	if initialData != nil {
		err := imageFile.rawFile.writeCluster(newClusterAddress, initialData)
		if err != nil {
			return 0, err
		}
	}
	return newClusterAddress, nil
}

// Get the offset of the given guest address in qcow2 file,
// the second return value specifies whether is cluster allocated or not.
func (imageFile *ImageFile) fileOffsetRead(address uint64) (uint64, bool, error) {
	if address >= imageFile.header.virtualDiskSizeBytes {
		return 0, false, fmt.Errorf(
			"address %d is bigger the virtual file size %d",
			address,
			imageFile.header.virtualDiskSizeBytes,
		)
	}
	clusterAddress, err := imageFile.pointerTable.readClusterAddress(address)
	if err != nil {
		if errors.Is(err, &ErrNeedPointerCluster{}) {
			return 0, false, nil
		}
		return 0, false, err
	}
	if clusterAddress == 0 {
		return 0, false, nil
	}
	result := clusterAddress + imageFile.rawFile.clusterOffset(address)
	return result, true, nil
}

// Gets the offset of the given guest address in the host file. If L1, L2, or data clusters need
// to be allocated, they will be.
func (imageFile *ImageFile) fileOffsetWrite(address uint64) (uint64, error) {
	if address >= imageFile.header.virtualDiskSizeBytes {
		return 0, fmt.Errorf(
			"address %d is bigger the virtual file size %d",
			address,
			imageFile.header.virtualDiskSizeBytes,
		)
	}
	referenceCountBeingSet := make([]referenceCountToSet, 0)
	clusterAddress, err := imageFile.pointerTable.readClusterAddress(address)
	if err != nil {
		if !errors.Is(err, &ErrNeedPointerCluster{}) {
			return 0, err
		}
		newL2ClusterAddress, err := imageFile.getNewCluster(nil)
		if err != nil {
			return 0, err
		}
		referenceCountBeingSet = append(
			referenceCountBeingSet,
			referenceCountToSet{
				address: newL2ClusterAddress,
				value:   1,
			},
		)
		err = imageFile.pointerTable.addNewPointerCluster(address, newL2ClusterAddress)
		if err != nil {
			return 0, err
		}
	}
	if clusterAddress == 0 {
		// initialize cluster data
		var initialData []uint8
		var err error
		if imageFile.backingFile != nil {
			// initialize cluster data with backing file data,
			// write can be partial.
			clusterBegin := address - (address % imageFile.header.clusterSize)
			data, err := imageFile.backingFile.ReadAt(clusterBegin, imageFile.header.clusterSize)
			if err != nil {
				return 0, err
			}
			initialData = data
		}
		clusterAddress, err = imageFile.appendDataCluster(initialData)
		if err != nil {
			return 0, err
		}
		err = imageFile.updateClusterAddress(address, clusterAddress, &referenceCountBeingSet)
		if err != nil {
			return 0, err
		}
	}
	for _, refCountToSet := range referenceCountBeingSet {
		unreferencedClusters, err := imageFile.setClusterRefcount(refCountToSet.address, refCountToSet.value)
		if err != nil {
			return 0, err
		}
		imageFile.unrefClusters = append(imageFile.unrefClusters, unreferencedClusters...)
	}
	result := clusterAddress + imageFile.rawFile.clusterOffset(address)
	return result, nil
}

func (imageFile *ImageFile) ReadAt(address, size uint64) ([]byte, error) {
	readCount := imageFile.limitRangeFile(address, size)
	numberBytesRead := uint64(0)
	buffer := bytes.NewBuffer(make([]byte, 0, size))
	for numberBytesRead < readCount {
		currentAddress := address + numberBytesRead
		fileOffset, ok, err := imageFile.fileOffsetRead(currentAddress)
		count := imageFile.rawFile.limitRangeCluster(currentAddress, readCount-numberBytesRead)
		if err != nil {
			return nil, err
		}
		if ok {
			tempBuffer := make([]byte, count)
			err = imageFile.rawFile.ReadAt(tempBuffer, int64(fileOffset))
			if err != nil {
				return nil, err
			}
			buffer.Write(tempBuffer)
		} else if imageFile.backingFile != nil {
			data, err := imageFile.backingFile.ReadAt(currentAddress, count)
			if err != nil {
				return nil, err
			}
			buffer.Write(data)
		} else {
			zeroes := make([]byte, count)
			buffer.Write(zeroes)
		}
		numberBytesRead += count
	}
	return buffer.Bytes(), nil
}

func (imageFile *ImageFile) WriteAt(address uint64, data []byte) error {
	if imageFile.readOnly {
		return newErrWriteAttemptToReadOnlyDisk(address, uint64(len(data)))
	}
	writeCount := imageFile.limitRangeFile(address, uint64(len(data)))
	numberBytesWritten := uint64(0)
	for numberBytesWritten < writeCount {
		currentAddress := address + numberBytesWritten
		offset, err := imageFile.fileOffsetWrite(currentAddress)
		if err != nil {
			return err
		}
		count := imageFile.rawFile.limitRangeCluster(currentAddress, writeCount-numberBytesWritten)
		err = imageFile.rawFile.WriteAt(
			data[numberBytesWritten:numberBytesWritten+count],
			int64(offset),
		)
		if err != nil {
			return err
		}
		numberBytesWritten += count
	}
	return nil
}

func (imageFile *ImageFile) Close() error {
	if imageFile.closed {
		return nil
	}
	var errOnSync error
	if !imageFile.readOnly {
		errOnSync = imageFile.syncCache()
	}
	if imageFile.backingFile != nil {
		err := imageFile.backingFile.Close()
		if err != nil {
			return err
		}
	}
	err := imageFile.rawFile.close()
	if errOnSync != nil {
		return errOnSync
	}
	imageFile.closed = true
	return err
}

func (imageFile *ImageFile) appendDataCluster(data []uint8) (uint64, error) {
	newAddress, err := imageFile.getNewCluster(data)
	if err != nil {
		return 0, err
	}
	newlyUnreferencedCluster, err := imageFile.setClusterRefcount(newAddress, 1)
	if err != nil {
		return 0, err
	}
	imageFile.unrefClusters = append(imageFile.unrefClusters, newlyUnreferencedCluster...)
	return newAddress, nil
}

// update l1 and l2 tables to point to the new cluster address
func (imageFile *ImageFile) updateClusterAddress(
	virtualAddress, clusterAddress uint64,
	referenceCountBeingSet *[]referenceCountToSet,
) error {
	err := imageFile.pointerTable.updateClusterAddress(virtualAddress, clusterAddress, func() (uint64, error) {
		return imageFile.getNewCluster(nil)
	})
	if errNeedFreeClusters, ok := err.(*ErrNeedFreeClusters); ok {
		*referenceCountBeingSet = append(*referenceCountBeingSet, errNeedFreeClusters.clustersToReferenceCount...)
		imageFile.unrefClusters = append(imageFile.unrefClusters, errNeedFreeClusters.clusterToRemove)
		return nil
	}
	return err
}

func (imageFile *ImageFile) syncCache() error {
	err := imageFile.pointerTable.sync()
	if err != nil {
		return err
	}
	err = imageFile.referenceCounts.flushBlocks()
	if err != nil {
		return err
	}
	err = imageFile.rawFile.sync()
	if err != nil {
		return err
	}
	syncRequired := false

	ok, err := imageFile.referenceCounts.flushTable()
	if err != nil {
		return err
	}
	syncRequired = syncRequired || ok
	ok, err = imageFile.pointerTable.syncL1()
	if err != nil {
		return err
	}
	syncRequired = syncRequired || ok
	if syncRequired {
		err = imageFile.rawFile.sync()
		if err != nil {
			return err
		}
	}
	return nil
}

func (imageFile *ImageFile) Flush() error {
	err := imageFile.syncCache()
	if err != nil {
		return err
	}
	for _, availCluster := range imageFile.unrefClusters {
		imageFile.availClusters = append(imageFile.availClusters, availCluster)
	}
	imageFile.unrefClusters = make([]uint64, 0, 100)
	return nil
}

func (imageFile ImageFile) Size() uint64 {
	return imageFile.header.virtualDiskSizeBytes
}

func (imageFile ImageFile) GetPath() string {
	return imageFile.fullImagePath
}
