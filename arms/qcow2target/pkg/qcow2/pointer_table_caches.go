// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package qcow2

import (
	"fmt"
)

type pointerTableCache interface {
	readClusterAddress(virtualAddress uint64) (uint64, error)
	addNewPointerCluster(virtualAddress, newClusterAddress uint64) error
	updateClusterAddress(
		virtualAddress,
		newClusterAddress uint64,
		obtainNewCluster func() (uint64, error),
	) error
	sync() error
	syncL1() (bool, error)
}

// Gets the offset of `address` in the L1 table.
func l1TableIndex(header ImageHeader, address uint64) uint64 {
	return (address / header.clusterSize) / uint64(header.l2Size)
}

// Gets the offset of `address` in the L2 table.
func l2TableIndex(header ImageHeader, address uint64) uint64 {
	return (address / header.clusterSize) % uint64(header.l2Size)
}

func readL2Cluster(rawFile QcowRawFile, clusterAddress uint64) ([]uint64, error) {
	l2PointerCluster, err := rawFile.readPointerCluster(clusterAddress, 0)
	if err != nil {
		return nil, err
	}
	for index, element := range l2PointerCluster {
		if element&CompressedFlag != 0 {
			return nil, fmt.Errorf("compressed clusters are not supported")
		}
		l2PointerCluster[index] &= L2TableOffsetMask
	}
	return l2PointerCluster, nil
}

type l1WriteBackCache struct {
	table   VectorCache[uint64]
	header  ImageHeader
	rawFile QcowRawFile
}

type pointerWriteBackCache struct {
	l1Table                         *l1WriteBackCache
	header                          ImageHeader
	rawFile                         QcowRawFile
	cache                           LruCacheMap[uint64, uint64]
	l2ClustersEvictedButNotL1Synced map[uint64]uint8
}

func (writeBackCache *l1WriteBackCache) getL2ClusterAddress(virtualAddress uint64) uint64 {
	l1Index := l1TableIndex(writeBackCache.header, virtualAddress)
	return writeBackCache.table.get(l1Index)
}

func (writeBackCache *l1WriteBackCache) setL2ClusterAddress(virtualAddress, newAddress uint64) uint64 {
	l1Index := l1TableIndex(writeBackCache.header, virtualAddress)
	writeBackCache.table.set(l1Index, newAddress)
	return writeBackCache.table.get(l1Index)
}

func (writeBackCache *l1WriteBackCache) markClean() {
	writeBackCache.table.markClean()
}

func (writeBackCache *l1WriteBackCache) getValues() []uint64 {
	return writeBackCache.table.getValues()
}

func (writeBackCache *l1WriteBackCache) dirty() bool {
	return writeBackCache.table.dirty()
}

func newL1WriteBackCache(header ImageHeader, rawFile QcowRawFile) (*l1WriteBackCache, error) {
	table, err := rawFile.readPointerTable(
		header.l1TableOffset,
		uint64(header.numL2Clusters),
		L1TableOffsetMask,
	)
	if err != nil {
		return nil, err
	}
	return &l1WriteBackCache{
		header:  header,
		table:   vectorCacheFromArray(table),
		rawFile: rawFile,
	}, nil
}

func newPointerWriteBackCache(header ImageHeader, rawFile QcowRawFile, cacheSize int) (pointerTableCache, error) {
	l1Table, err := newL1WriteBackCache(header, rawFile)
	if err != nil {
		return nil, err
	}
	return &pointerWriteBackCache{
		l1Table:                         l1Table,
		header:                          header,
		cache:                           newCacheMap[uint64, uint64](uint64(cacheSize)),
		rawFile:                         rawFile,
		l2ClustersEvictedButNotL1Synced: map[uint64]uint8{},
	}, nil
}

func (writeBackCache *pointerWriteBackCache) readClusterAddress(virtualAddress uint64) (uint64, error) {
	l2ClusterAddress := writeBackCache.l1Table.getL2ClusterAddress(virtualAddress)
	if l2ClusterAddress == 0 {
		return 0, &ErrNeedPointerCluster{}
	}
	if !writeBackCache.cache.containsKey(l2ClusterAddress) {
		data, err := readL2Cluster(writeBackCache.rawFile, l2ClusterAddress)
		if err != nil {
			return 0, err
		}
		l2Cluster := vectorCacheFromArray[uint64](data)
		err = writeBackCache.cache.insert(
			l2ClusterAddress,
			l2Cluster,
			func(index uint64, evicted VectorCache[uint64]) error {
				if writeBackCache.rawFile.isReadOnly() {
					return nil
				}
				writeBackCache.l2ClustersEvictedButNotL1Synced[index] = 1
				return writeBackCache.rawFile.writePointerTable(
					index,
					evicted.getValues(),
					ClusterUsedFlag,
				)
			},
		)
		if err != nil {
			return 0, err
		}
	}
	l2Cluster, _ := writeBackCache.cache.get(l2ClusterAddress)
	clusterAddress := l2Cluster.get(l2TableIndex(writeBackCache.header, virtualAddress))
	return clusterAddress, nil
}

func (writeBackCache *pointerWriteBackCache) addNewPointerCluster(virtualAddress, newClusterAddress uint64) error {
	// newAddress is an address of L2 cluster, which was previously allocated
	l2ClusterAddress := writeBackCache.l1Table.setL2ClusterAddress(virtualAddress, newClusterAddress)
	l2Cluster := newVectorCache[uint64](uint64(writeBackCache.header.l2Size))
	err := writeBackCache.cache.insert(
		l2ClusterAddress,
		l2Cluster,
		func(index uint64, evicted VectorCache[uint64]) error {
			writeBackCache.l2ClustersEvictedButNotL1Synced[index] = 1
			return writeBackCache.rawFile.writePointerTable(
				index,
				evicted.getValues(),
				ClusterUsedFlag,
			)
		},
	)
	return err
}

func (writeBackCache pointerWriteBackCache) l2clusterAddressWasPreviouslyReadButL1NotSynced(address uint64) bool {
	// L2 update mechanism for already allocated (read from disk in previous operation,
	// or in any other ways was present on disk and having values) requires copy-on write,
	// since if we update L2 cluster without updating L1 table.
	// This way, writing to a file becomes transactional.
	// If you cancel write in the middle, newly allocated L2 tables won't be
	// reference counted and L1 table would point to an old L2 cluster which remains unchanged.
	// So the only difference in file would be a bunch of a newly allocated clusters with the same reference
	// count.
	// But if we read a L2 table to the cache, reallocated it into new cluster, and then
	// the table gets evicted from the cache and newly written to the disk,
	// at the next l2 address update of the same cluster it would be reallocated, but
	// l1 table is not flushed, so there would be just another allocation.
	// To avoid this leak scenery, store all evicted l2 cluster addresses in hash map,
	// and not allocate new l2 clusters, but write to existing once if the cluster was flushed before l1
	// table sync. The same logic applies to a two level reference count table.
	_, ok := writeBackCache.l2ClustersEvictedButNotL1Synced[address]
	return ok
}

func (writeBackCache *pointerWriteBackCache) updateClusterAddress(
	virtualAddress, newClusterAddress uint64,
	obtainNewCluster func() (uint64, error),
) error {
	l2ClusterAddress := writeBackCache.l1Table.getL2ClusterAddress(virtualAddress)
	cachedL2Item, _ := writeBackCache.cache.get(l2ClusterAddress)
	// item is not dirty only if l2 table cluster is
	// present on the disk, and we need to change the address
	if !cachedL2Item.dirty() && !writeBackCache.l2clusterAddressWasPreviouslyReadButL1NotSynced(l2ClusterAddress) {
		// We do not change the address on the same L2 table block, but allocate
		// a new L2 table block, and point L1 table to a new blocks address.
		// This way, we can commit L1 table after all L2 table blocks, and it will
		// always be pointing to valid data.
		needFreeClustersErr := &ErrNeedFreeClusters{
			clusterToRemove:          l2ClusterAddress,
			clustersToReferenceCount: make([]referenceCountToSet, 0, 2),
		}
		newL2TableClusterAddress, err := obtainNewCluster()
		if err != nil {
			return err
		}
		writeBackCache.l1Table.setL2ClusterAddress(virtualAddress, newL2TableClusterAddress)
		needFreeClustersErr.clustersToReferenceCount = append(
			needFreeClustersErr.clustersToReferenceCount,
			referenceCountToSet{address: l2ClusterAddress, value: 0},
		)
		needFreeClustersErr.clustersToReferenceCount = append(
			needFreeClustersErr.clustersToReferenceCount,
			referenceCountToSet{address: newL2TableClusterAddress, value: 1},
		)
		err = writeBackCache.cache.remove(l2ClusterAddress)
		if err != nil {
			return err
		}
		cachedL2Item.set(l2TableIndex(writeBackCache.header, virtualAddress), newClusterAddress)
		err = writeBackCache.cache.set(newL2TableClusterAddress, *cachedL2Item)
		if err != nil {
			return err
		}
		return needFreeClustersErr
	}
	cachedL2Item.set(l2TableIndex(writeBackCache.header, virtualAddress), newClusterAddress)
	return nil
}

func (writeBackCache *pointerWriteBackCache) sync() error {
	for address, l2Table := range writeBackCache.cache.store {
		if !l2Table.data.dirty() {
			continue
		}
		if address != 0 {
			err := writeBackCache.rawFile.writePointerTable(
				address,
				l2Table.data.getValues(),
				ClusterUsedFlag,
			)
			if err != nil {
				return err
			}
		} else {
			return fmt.Errorf("invalid address value 0")
		}
		l2Table.data.markClean()
	}
	return nil
}

func (writeBackCache *pointerWriteBackCache) syncL1() (bool, error) {
	if writeBackCache.l1Table.dirty() {
		err := writeBackCache.rawFile.writePointerTable(
			writeBackCache.header.l1TableOffset,
			writeBackCache.l1Table.getValues(),
			0,
		)
		if err != nil {
			return false, err
		}
		writeBackCache.l2ClustersEvictedButNotL1Synced = map[uint64]uint8{}
		writeBackCache.l1Table.markClean()
		return true, nil
	} else {
		return false, nil
	}
}

type l1NoCache struct {
	header  ImageHeader
	rawFile QcowRawFile
}

func l2ClusterAddressOffsetInFile(header ImageHeader, virtualAddress uint64) uint64 {
	l1Index := l1TableIndex(header, virtualAddress)
	return header.l1TableOffset + 8*l1Index
}
func (l1Table *l1NoCache) getL2ClusterAddress(virtualAddress uint64) (uint64, error) {
	offset := l2ClusterAddressOffsetInFile(l1Table.header, virtualAddress)
	return l1Table.rawFile.readUint64At(offset)
}

func (l1Table *l1NoCache) setL2ClusterAddress(virtualAddress, newL2TableClusterAddress uint64) (uint64, error) {
	offset := l2ClusterAddressOffsetInFile(l1Table.header, virtualAddress)
	err := l1Table.rawFile.writeUint64At(newL2TableClusterAddress, offset)
	if err != nil {
		return 0, err
	}
	return newL2TableClusterAddress, nil
}

type pointerTableNoCache struct {
	l1Table *l1NoCache
	header  ImageHeader
	rawFile QcowRawFile
}

func (pointerTable *pointerTableNoCache) readClusterAddress(virtualAddress uint64) (uint64, error) {
	l2ClusterAddress, err := pointerTable.l1Table.getL2ClusterAddress(virtualAddress)
	if err != nil {
		return 0, err
	}
	if l2ClusterAddress == 0 {
		return 0, &ErrNeedPointerCluster{}
	}
	indexInL2Table := l2TableIndex(pointerTable.header, virtualAddress)
	offset := l2ClusterAddress + 8*indexInL2Table
	clusterAddress, err := pointerTable.rawFile.readUint64At(offset)
	return clusterAddress, err
}

func (pointerTable *pointerTableNoCache) addNewPointerCluster(virtualAddress, newClusterAddress uint64) error {
	_, err := pointerTable.l1Table.setL2ClusterAddress(virtualAddress, newClusterAddress)
	return err
}

func (pointerTable *pointerTableNoCache) updateClusterAddress(
	virtualAddress,
	newClusterAddress uint64,
	obtainNewCluster func() (uint64, error),
) error {
	l2ClusterAddress, err := pointerTable.l1Table.getL2ClusterAddress(virtualAddress)
	if err != nil {
		return err
	}
	indexInL2Table := l2TableIndex(pointerTable.header, virtualAddress)
	offset := l2ClusterAddress + 8*indexInL2Table
	err = pointerTable.rawFile.writeUint64At(newClusterAddress, offset)
	if err != nil {
		return err
	}
	return nil
}

func (pointerTable *pointerTableNoCache) sync() error {
	return nil
}

func (pointerTable *pointerTableNoCache) syncL1() (bool, error) {
	return false, nil
}

func newPointerTableNoCache(header ImageHeader, rawFile QcowRawFile) (pointerTableCache, error) {
	l1Table := &l1NoCache{header, rawFile}
	return &pointerTableNoCache{
		l1Table: l1Table,
		header:  header,
		rawFile: rawFile,
	}, nil
}

func newPointerTable(header ImageHeader, rawFile QcowRawFile, useCache bool, cacheSize int) (pointerTableCache, error) {
	if useCache {
		return newPointerWriteBackCache(header, rawFile, cacheSize)
	} else {
		return newPointerTableNoCache(header, rawFile)
	}
}
