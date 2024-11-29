// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package qcow2

import (
	"fmt"
	"path/filepath"
)

type ErrNeedNewCluster struct{}

func (n *ErrNeedNewCluster) Error() string {
	return "need a new cluster"
}

type ErrNeedReadCluster struct {
	address uint64
}

func (n *ErrNeedReadCluster) Error() string {
	return "need to read a cluster"
}

type ErrNeedPointerCluster struct {
}

func (needPointerCluster ErrNeedPointerCluster) Error() string {
	return "need new pointer cluster"
}

func (needPointerCluster *ErrNeedPointerCluster) Is(err error) bool {
	_, ok := err.(*ErrNeedPointerCluster)
	return ok
}

type ErrNeedFreeClusters struct {
	clustersToReferenceCount []referenceCountToSet
	clusterToRemove          uint64
}

func (needFreeClusters ErrNeedFreeClusters) Error() string {
	return "need free clusters"
}

type ErrReadOnlyImageBrokenReferenceCounts struct {
}

func (err ErrReadOnlyImageBrokenReferenceCounts) Error() string {
	return "image is read only, can't rebuild reference counts"
}

func newErrReadOnlyImageBrokenReferenceCounts() error {
	return &ErrReadOnlyImageBrokenReferenceCounts{}
}

type ErrWriteAttemptToReadOnlyDisk struct {
	at   uint64
	size uint64
}

func (err ErrWriteAttemptToReadOnlyDisk) Error() string {
	return fmt.Sprintf(
		"image is read only, can't write at %d, with data size %d",
		err.at,
		err.size,
	)
}

func newErrWriteAttemptToReadOnlyDisk(
	at uint64,
	size uint64,
) error {
	return &ErrWriteAttemptToReadOnlyDisk{
		at:   at,
		size: size,
	}
}

type ErrAttemptToSyncReadOnlyFile struct {
}

func (err ErrAttemptToSyncReadOnlyFile) Error() string {
	return "attempt to sync read only backing file"
}

func newErrAttemptToSyncReadOnlyFile() error {
	return &ErrAttemptToSyncReadOnlyFile{}
}

type ErrAttemptToTruncateReadOnlyFile struct{}

func (err ErrAttemptToTruncateReadOnlyFile) Error() string {
	return "attempt to resize read only file with Truncate"
}

func newErrAttemptToTruncateReadOnlyFile() error {
	return &ErrAttemptToTruncateReadOnlyFile{}
}

type ErrParentDiskDoesNotExist struct {
	parentPath    string
	diskPath      string
	diskDirectory string
}

func newErrParentDiskDoesNotExist(
	parentPath string,
	diskPath string,
) error {
	return &ErrParentDiskDoesNotExist{
		parentPath:    parentPath,
		diskPath:      diskPath,
		diskDirectory: filepath.Dir(diskPath),
	}
}

func (err ErrParentDiskDoesNotExist) Error() string {
	return fmt.Sprintf(
		"couldn't find parent disk by path '%s', for child disk '%s',"+
			" attempted as absolute path and as relative path to %s",
		err.parentPath,
		err.diskPath,
		err.diskDirectory,
	)
}

type ErrDiskDirectoryDoesNotExist struct {
	diskDirectory string
}

func newErrDiskDirectoryDoesNotExist(
	diskDirectory string,
) error {
	return &ErrDiskDirectoryDoesNotExist{
		diskDirectory: filepath.Dir(diskDirectory),
	}
}

func (err ErrDiskDirectoryDoesNotExist) Error() string {
	return fmt.Sprintf(
		"disk directory '%s' does not exist",
		err.diskDirectory,
	)
}

type ErrRecursionDepthExceeded struct {
	recursionDepth uint32
}

func newErrRecursionDepthExceeded(depth uint32) error {
	return &ErrRecursionDepthExceeded{recursionDepth: depth}
}

func (err ErrRecursionDepthExceeded) Error() string {
	return fmt.Sprintf(
		"recursion depth %d is exceeded",
		err.recursionDepth,
	)
}

func newNonAbsolutePathError(diskPath string) error {
	return &NonAbsolutePathError{
		diskPath: diskPath,
	}
}

type NonAbsolutePathError struct {
	diskPath string
}

func (e NonAbsolutePathError) Error() string {
	return fmt.Sprintf("%s is not absolute", e.diskPath)
}
