// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package qcow2

import "fmt"

func rebuildReferenceCounts(rawFile QcowRawFile, header ImageHeader) error {
	// todo handle maxValidClusterIndex comparison (probably wrong)
	referenceCountBits := uint64(1) << header.refCountOrder
	referenceCountBytes := divRoundUp[uint64](referenceCountBits, 8)
	referenceCountBlockEntries := header.clusterSize / referenceCountBytes
	maxClusters := uint64(header.l1Clusters + header.numL2Clusters + header.numClusters + 1) // 1 header cluster
	referenceBlockClusters := divRoundUp[uint64](maxClusters, referenceCountBlockEntries)
	pointersPerCluster := header.clusterSize / 8
	referenceCountTableClusters := divRoundUp[uint64](referenceBlockClusters, pointersPerCluster)
	// Block number to store reference count table
	// and reference count table clusters
	referenceCountBlockForReferenceCount := divRoundUp[uint64](
		referenceBlockClusters+referenceCountTableClusters,
		referenceCountBlockEntries,
	)
	referenceCountTableClustersForReferenceCounts := divRoundUp[uint64](
		referenceCountBlockForReferenceCount,
		referenceCountBlockEntries)
	maxValidClusterIndex := maxClusters + referenceBlockClusters +
		referenceCountTableClusters + referenceCountBlockForReferenceCount +
		referenceCountTableClustersForReferenceCounts
	if maxValidClusterIndex > L1TableMaxSize {
		return fmt.Errorf(
			"invalid reference count table size %d",
			maxValidClusterIndex,
		)
	}
	maxValidClusterOffset := maxValidClusterIndex * header.clusterSize
	size, err := rawFile.size()
	if err != nil {
		return fmt.Errorf("error while getting file size %d", err)
	}
	if maxValidClusterOffset < size-header.clusterSize {
		return fmt.Errorf("invalid reference count offset")
	}
	referenceCounts := make([]uint16, maxValidClusterIndex)

	err = setHeaderReferenceCount(referenceCounts, header.clusterSize)
	if err != nil {
		return err
	}
	err = setL1ReferenceCounts(referenceCounts, header)
	if err != nil {
		return err
	}
	err = setDataReferenceCounts(referenceCounts, header, rawFile)
	if err != nil {
		return err
	}
	err = setReferenceCountTableClusters(referenceCounts, header)
	if err != nil {
		return err
	}
	referenceTable, err := allocateReferenceCountBlocks(
		header,
		referenceCounts,
		referenceBlockClusters,
	)
	if err != nil {
		return err
	}
	err = writeReferenceCountBlocks(
		referenceCounts,
		header,
		referenceTable,
		rawFile,
		referenceCountBlockEntries,
	)
	return err
}

func addReferenceCount(referenceCounts []uint16, clusterSize uint64, clusterAddress uint64) error {
	idx := clusterAddress / clusterSize
	if idx >= uint64(len(referenceCounts)) {
		return fmt.Errorf(
			"wrong index %d, maximum ref counts size is %d",
			idx,
			len(referenceCounts),
		)
	}
	referenceCounts[idx] += 1
	return nil
}

// Add a reference to the first cluster(header plus extensions)
func setHeaderReferenceCount(
	referenceCounts []uint16,
	clusterSize uint64,
) error {
	return addReferenceCount(referenceCounts, clusterSize, 0)
}

// Add reference to L1 table clusters
func setL1ReferenceCounts(
	referenceCounts []uint16,
	header ImageHeader,
) error {
	for i := uint64(0); i < uint64(header.l1Clusters); i += 1 {
		err := addReferenceCount(
			referenceCounts,
			header.clusterSize,
			header.l1TableOffset+i*header.clusterSize,
		)
		if err != nil {
			return err
		}
	}
	return nil
}

// Traverse L1 and L2 tables to find all reachable data clusters
func setDataReferenceCounts(
	referenceCounts []uint16,
	header ImageHeader,
	rawFile QcowRawFile,
) error {
	l1Table, err := rawFile.readPointerTable(
		header.l1TableOffset,
		uint64(header.l1Size),
		L1TableOffsetMask,
	)
	if err != nil {
		return err
	}
	for l1Index := uint32(0); l1Index < header.l1Size; l1Index += 1 {
		l2AddressOnDisk := l1Table[l1Index]
		if l2AddressOnDisk != 0 {
			err = addReferenceCount(referenceCounts, header.clusterSize, l2AddressOnDisk)
			if err != nil {
				return err
			}
			l2Table, err := rawFile.readPointerTable(
				l2AddressOnDisk,
				header.clusterSize/8, // where 8 is size of uint64
				L2TableOffsetMask,
			)
			if err != nil {
				return err
			}
			for _, dataClusterAddress := range l2Table {
				if dataClusterAddress != 0 {
					err = addReferenceCount(referenceCounts, header.clusterSize, dataClusterAddress)
					if err != nil {
						return err
					}
				}
			}
		}
	}
	return nil
}

// Add references to the top-level reference count table clusters
func setReferenceCountTableClusters(
	referenceCounts []uint16,
	header ImageHeader,
) error {
	for i := uint32(0); i < header.refCountTableClusters; i += 1 {
		err := addReferenceCount(
			referenceCounts,
			header.clusterSize,
			header.refCountTableOffset+uint64(i)*header.clusterSize,
		)
		if err != nil {
			return err
		}
	}
	return nil
}

// Allocate clusters for reference count blocks
// This needs to be done after obtaining
// all reference counts and allocating all other clusters
func allocateReferenceCountBlocks(
	header ImageHeader,
	referenceCounts []uint16,
	referenceBlockClusters uint64,
) ([]uint64, error) {
	pointersPerClusters := header.clusterSize / 8
	referenceCountTableEntries := divRoundUp[uint64](referenceBlockClusters, pointersPerClusters)
	referenceCountTable := make([]uint64, referenceCountTableEntries)
	firstFreeCluster := uint64(0)
	for referenceCountBlockAddress := range referenceCountTable {
		for {
			if firstFreeCluster >= uint64(len(referenceCounts)) {
				return nil, fmt.Errorf("not enough space for reference counts")
			}
			if referenceCounts[firstFreeCluster] == 0 {
				break
			}
			firstFreeCluster += 1
		}
		referenceCountTable[referenceCountBlockAddress] = firstFreeCluster * header.clusterSize
		err := addReferenceCount(
			referenceCounts,
			header.clusterSize,
			referenceCountTable[referenceCountBlockAddress],
		)
		if err != nil {
			return nil, err
		}
		firstFreeCluster += 1
	}
	return referenceCountTable, nil
}

func writeReferenceCountBlocks(
	referenceCounts []uint16,
	header ImageHeader,
	referenceTable []uint64,
	rawFile QcowRawFile,
	referenceCountBlockEntries uint64,
) error {
	header.compatibleFeatures = header.compatibleFeatures | compatibleFeaturesLazyRefcounts
	err := rawFile.writeHeader(header)
	if err != nil {
		return err
	}
	for index, referenceCountBlockAdress := range referenceTable {
		referenceCountBlockStart := uint64(index) * referenceCountBlockEntries
		referenceCountBlockEnd := referenceCountBlockStart + referenceCountBlockEntries
		if uint64(len(referenceCounts)) < referenceCountBlockEnd {
			referenceCountBlockEnd = uint64(len(referenceCounts))
		}
		referenceCountBlock := referenceCounts[referenceCountBlockStart:referenceCountBlockEnd]
		err = rawFile.writeRefcountBlock(referenceCountBlockAdress, referenceCountBlock)
		if err != nil {
			return err
		}
		// Last (partial) cluster must be aligned to a cluster size
		if uint64(len(referenceCountBlock)) < referenceCountBlockEntries {
			referenceCountBlockPadding := make(
				[]uint16, referenceCountBlockEntries-uint64(len(referenceCountBlock)))
			err = rawFile.writeRefcountBlock(
				referenceCountBlockAdress+uint64(len(referenceCountBlock)*2),
				referenceCountBlockPadding,
			)
			if err != nil {
				return err
			}
		}
	}
	err = rawFile.writePointerTable(header.refCountTableOffset, referenceTable, 0)
	if err != nil {
		return err
	}
	header.compatibleFeatures &= ^compatibleFeaturesLazyRefcounts
	err = rawFile.writeHeader(header)
	return err
}
