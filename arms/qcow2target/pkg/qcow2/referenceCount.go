// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package qcow2

import (
	"fmt"
)

type ReferenceCountTable interface {
	setClusterRefcount(
		clusterAddress uint64,
		refcount uint16,
		newCluster *newCluster,
	) (uint64, bool, error)
	getClusterRefcount(address uint64) (uint16, error)
	flushBlocks() error
	flushTable() (bool, error)
	maxValidClusterOffset() uint64
	referenceCountsPerBlock() uint64
}
type ReferenceCountWriteBack struct {
	rawFile                                              QcowRawFile
	table                                                VectorCache[uint64]
	offset                                               uint64
	referenceBlockCache                                  LruCacheMap[uint64, uint16]
	numberOfReferenceCountsInCluster                     uint64
	clusterSize                                          uint64
	_maxValidClusterOffset                               uint64
	referenceCountClustersEvictedFromCacheNotTableSynced map[uint64]uint8
}

func (referenceCount ReferenceCountWriteBack) maxValidClusterOffset() uint64 {
	return referenceCount._maxValidClusterOffset
}

func newReferenceCountWriteBack(
	rawFile QcowRawFile,
	refcountTableOffset uint64,
	refcountTableEntries uint64,
	refcountBlockEntries uint64,
	clusterSize uint64,
	cacheSize int,
) (ReferenceCountTable, error) {
	tableData, err := rawFile.readPointerTable(
		refcountTableOffset,
		refcountTableEntries,
		0,
	)
	if err != nil {
		return nil, err
	}
	table := vectorCacheFromArray(tableData)
	maxValidClusterIndex := table.len()*refcountBlockEntries - 1
	maxValidClusterOffset := maxValidClusterIndex * clusterSize
	return &ReferenceCountWriteBack{
		rawFile:                          rawFile,
		table:                            table,
		offset:                           refcountTableOffset,
		referenceBlockCache:              newCacheMap[uint64, uint16](uint64(cacheSize)),
		numberOfReferenceCountsInCluster: refcountBlockEntries,
		clusterSize:                      clusterSize,
		_maxValidClusterOffset:           maxValidClusterOffset,
		referenceCountClustersEvictedFromCacheNotTableSynced: map[uint64]uint8{},
	}, nil
}

// Returns the number of reference counts per block.
func (referenceCount ReferenceCountWriteBack) referenceCountsPerBlock() uint64 {
	return referenceCount.numberOfReferenceCountsInCluster
}

type newCluster struct {
	clusterAddress      uint64
	referenceCountBlock VectorCache[uint16]
}

func (referenceCount ReferenceCountWriteBack) referenceCountClusterAddressWasPreviouslyReadButTableNotSynced(
	index uint64) bool {
	// the same as l2clusterAddressWasPreviouslyReadButL1NotSynced for pointer table
	// write back cache, see comment there.
	_, ok := referenceCount.referenceCountClustersEvictedFromCacheNotTableSynced[index]
	return ok
}

// Returns `ErrNeedNewCluster` if a new cluster needs to be allocated for reference counts. If an
// existing cluster needs to be read, `NeedCluster(addr)` is returned. The Caller should
// allocate a cluster or read the required one and call this function again with the cluster.
// On success, an optional address of a dropped cluster is returned. The dropped cluster can
// be reused for other purposes.
func (referenceCount *ReferenceCountWriteBack) setClusterRefcount(
	clusterAddress uint64,
	refcount uint16,
	newCluster *newCluster,
) (uint64, bool, error) {
	tableIndex, blockIndex := referenceCount.getRefcountIndex(clusterAddress)
	blockAddrDisk := referenceCount.table.get(tableIndex)

	// Fill the cache if this block isn't yet there.
	if !referenceCount.referenceBlockCache.containsKey(tableIndex) {
		// Need a new cluster
		if newCluster != nil {
			address := newCluster.clusterAddress
			table := newCluster.referenceCountBlock
			referenceCount.table.set(tableIndex, address)
			err := referenceCount.referenceBlockCache.insert(
				tableIndex, table, func(index uint64, evicted VectorCache[uint16]) error {
					referenceCount.referenceCountClustersEvictedFromCacheNotTableSynced[index] = 1
					err := referenceCount.rawFile.writeRefcountBlock(referenceCount.table.get(index), evicted.getValues())
					return err
				})
			if err != nil {
				return 0, false, err
			}
		} else {
			if blockAddrDisk == 0 {
				return 0, false, &ErrNeedNewCluster{}
			}
			return 0, false, &ErrNeedReadCluster{address: blockAddrDisk}
		}
	}
	var droppedCluster uint64
	var droppedClusterHasValue bool
	// Access item as safe since we have previously
	// set cache value
	refBlockItem, _ := referenceCount.referenceBlockCache.get(tableIndex)
	l1TableSynced := referenceCount.referenceCountClusterAddressWasPreviouslyReadButTableNotSynced(tableIndex)
	if !refBlockItem.dirty() && !l1TableSynced {
		if newCluster != nil {
			referenceCount.table.set(tableIndex, newCluster.clusterAddress)
			droppedCluster = blockAddrDisk
			droppedClusterHasValue = true
		} else {
			return 0, false, &ErrNeedNewCluster{}
		}
	}
	cache, _ := referenceCount.referenceBlockCache.get(tableIndex)
	cache.set(blockIndex, refcount)
	return droppedCluster, droppedClusterHasValue, nil
}

// Flush the dirty refcount blocks. This must be done before flushing the table that points to
// the blocks.
func (referenceCount *ReferenceCountWriteBack) flushBlocks() error {
	// Write out all dirty L2 tables.
	for tableIndex, block := range referenceCount.referenceBlockCache.store {
		address := referenceCount.table.get(tableIndex)
		if address != 0 {
			err := referenceCount.rawFile.writeRefcountBlock(address, block.data.getValues())
			if err != nil {
				return err
			}
		} else {
			return fmt.Errorf("zero address while flushing the block")
		}
		block.data.markClean()
	}
	return nil
}

// Flush the refcount table that keeps the address of the reference counts blocks.
// Returns true if the table changed since the previous `flush_table()` call.
func (referenceCount *ReferenceCountWriteBack) flushTable() (bool, error) {
	if referenceCount.table.dirty() {
		err := referenceCount.rawFile.writePointerTable(
			referenceCount.offset,
			referenceCount.table.getValues(),
			0,
		)
		if err != nil {
			return false, err
		}
		referenceCount.referenceCountClustersEvictedFromCacheNotTableSynced = map[uint64]uint8{}
		referenceCount.table.markClean()
		return true, nil
	} else {
		return false, nil
	}
}

// Gets the refcount for a cluster with the given address.
func (referenceCount *ReferenceCountWriteBack) getClusterRefcount(
	address uint64,
) (uint16, error) {
	tableIndex, blockIndex := referenceCount.getRefcountIndex(address)
	blockAddrDisk := referenceCount.table.get(tableIndex)
	if blockAddrDisk == 0 {
		return 0, nil
	}
	if !referenceCount.referenceBlockCache.containsKey(tableIndex) {
		refCountBlock, err := referenceCount.rawFile.readRefCountBlock(blockAddrDisk)
		if err != nil {
			return 0, err
		}
		table := vectorCacheFromArray(refCountBlock)
		err = referenceCount.referenceBlockCache.insert(
			tableIndex,
			table,
			func(index uint64, evicted VectorCache[uint16]) error {
				if referenceCount.rawFile.isReadOnly() {
					return nil
				}
				referenceCount.referenceCountClustersEvictedFromCacheNotTableSynced[index] = 1
				err := referenceCount.rawFile.writeRefcountBlock(
					referenceCount.table.get(index),
					evicted.getValues(),
				)
				return err
			},
		)
		if err != nil {
			return 0, err
		}
	}
	value, ok := referenceCount.referenceBlockCache.get(tableIndex)
	if !ok {
		return 0, fmt.Errorf("table index not found in cache %d", tableIndex)
	}
	return value.get(blockIndex), nil
}

// Gets the address of the refcount block and the index into the block for the given address.
func (referenceCount ReferenceCountWriteBack) getRefcountIndex(address uint64) (refcountBlock uint64, indexIntoBlock uint64) {
	return getRefcountIndex(address, referenceCount.clusterSize, referenceCount.numberOfReferenceCountsInCluster)
}

func getRefcountIndex(address, clusterSize, numberOfReferenceCountsInCluster uint64) (refcountBlock uint64, indexIntoBlock uint64) {
	indexIntoBlock = (address / clusterSize) % numberOfReferenceCountsInCluster
	refcountBlock = (address / clusterSize) / numberOfReferenceCountsInCluster
	return
}

type ReferenceCountNoCache struct {
	rawFile                          QcowRawFile
	offset                           uint64
	numberOfReferenceCountsInCluster uint64
	clusterSize                      uint64
	_maxValidClusterOffset           uint64
}

func (referenceCount ReferenceCountNoCache) maxValidClusterOffset() uint64 {
	return referenceCount._maxValidClusterOffset
}

func (referenceCount ReferenceCountNoCache) setClusterRefcount(
	clusterAddress uint64,
	refcount uint16,
	newCluster *newCluster,
) (uint64, bool, error) {
	tableIndex, blockIndex := getRefcountIndex(
		clusterAddress,
		referenceCount.clusterSize,
		referenceCount.numberOfReferenceCountsInCluster,
	)
	uint16Size := uint64(2)
	uint64Size := uint64(8)
	blockAddrDisk, err := referenceCount.rawFile.readUint64At(
		referenceCount.offset + uint64Size*tableIndex,
	)
	if err != nil {
		return 0, false, err
	}
	if newCluster != nil {
		address := newCluster.clusterAddress
		table := newCluster.referenceCountBlock
		err := referenceCount.rawFile.writeRefcountBlock(address, table.getValues())
		if err != nil {
			return 0, false, err
		}
		err = referenceCount.rawFile.writeUint64At(
			address,
			referenceCount.offset+uint64Size*tableIndex,
		)
		blockAddrDisk = address
	} else if blockAddrDisk == 0 {
		return 0, false, &ErrNeedNewCluster{}
	}
	err = referenceCount.rawFile.writeUint16At(
		refcount,
		blockAddrDisk+blockIndex*uint16Size,
	)
	return 0, false, nil
}

func (referenceCount ReferenceCountNoCache) getClusterRefcount(address uint64) (uint16, error) {
	tableIndex, blockIndex := getRefcountIndex(
		address,
		referenceCount.clusterSize,
		referenceCount.numberOfReferenceCountsInCluster,
	)
	uint16Size := uint64(2)
	uint64Size := uint64(8)
	blockAddrDisk, err := referenceCount.rawFile.readUint64At(
		referenceCount.offset + uint64Size*tableIndex,
	)
	if err != nil {
		return 0, err
	}
	if blockAddrDisk == 0 {
		return 0, nil
	}
	return referenceCount.rawFile.readUint16At(blockAddrDisk + uint16Size*blockIndex)
}

func (referenceCount ReferenceCountNoCache) flushBlocks() error {
	return nil
}

func (referenceCount ReferenceCountNoCache) flushTable() (bool, error) {
	return false, nil
}

func (referenceCount ReferenceCountNoCache) referenceCountsPerBlock() uint64 {
	return referenceCount.numberOfReferenceCountsInCluster
}

func newReferenceCountNoCache(
	rawFile QcowRawFile,
	refcountTableOffset uint64,
	refcountTableEntries uint64,
	refcountBlockEntries uint64,
	clusterSize uint64,
) ReferenceCountTable {
	maxValidClusterIndex := refcountTableEntries*refcountBlockEntries - 1
	maxValidClusterOffset := maxValidClusterIndex * clusterSize
	return &ReferenceCountNoCache{
		rawFile:                          rawFile,
		offset:                           refcountTableOffset,
		numberOfReferenceCountsInCluster: refcountBlockEntries,
		clusterSize:                      clusterSize,
		_maxValidClusterOffset:           maxValidClusterOffset,
	}
}

func newReferenceCount(
	rawFile QcowRawFile,
	refcountTableOffset uint64,
	refcountTableEntries uint64,
	refcountBlockEntries uint64,
	clusterSize uint64,
	useCache bool,
	cacheSize int,
) (ReferenceCountTable, error) {
	if useCache {
		return newReferenceCountWriteBack(
			rawFile,
			refcountTableOffset,
			refcountTableEntries,
			refcountBlockEntries,
			clusterSize,
			cacheSize,
		)
	} else {
		return newReferenceCountNoCache(
			rawFile,
			refcountTableOffset,
			refcountTableEntries,
			refcountBlockEntries,
			clusterSize,
		), nil
	}
}
