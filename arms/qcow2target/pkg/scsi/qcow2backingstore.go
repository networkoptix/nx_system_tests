// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package scsi

import (
	"qcow2target/pkg/qcow2"
)

const (
	Qcow2BackingStorage = "qcow2"
)

type Qcow2BackingStore struct {
	Name            string
	DataSize        uint64
	OflagsSupported int
	image           *qcow2.ImageFile
	imageFactory    *qcow2.ImageFactory
}

func NewQcow2BackingStore(imageFactory *qcow2.ImageFactory) (BackingStore, error) {
	return &Qcow2BackingStore{
		Name:            Qcow2BackingStorage,
		DataSize:        0,
		OflagsSupported: 0,
		imageFactory:    imageFactory,
	}, nil
}

func (backingStore *Qcow2BackingStore) Open(path string) error {
	img, err := backingStore.imageFactory.OpenImage(path, 10)
	if err != nil {
		return err
	}
	backingStore.image = img
	backingStore.DataSize = backingStore.image.Size()
	return nil
}

func (backingStore *Qcow2BackingStore) Close() error {
	return backingStore.image.Close()
}

func (backingStore *Qcow2BackingStore) Init() error {
	return nil
}

func (backingStore *Qcow2BackingStore) Exit() error {
	return nil
}

func (backingStore *Qcow2BackingStore) Size() uint64 {
	return backingStore.image.Size()
}

func (backingStore *Qcow2BackingStore) Read(offset, transferLength uint64) ([]byte, error) {
	return backingStore.image.ReadAt(offset, transferLength)
}

func (backingStore *Qcow2BackingStore) Write(writeBuffer []byte, offset uint64) error {
	return backingStore.image.WriteAt(offset, writeBuffer)
}

func (backingStore *Qcow2BackingStore) DataSync() error {
	return backingStore.image.Flush()
}

func (backingStore *Qcow2BackingStore) DataAdvise() error {
	// From SBC4r15:
	// The PRE-FETCH (10) command (see table 74) requests that the device server:
	// a) for any mapped LBAs specified by the command that are not already contained in cache, perform
	// read medium operations and write cache operations (see 4.15); and
	// b) for any unmapped LBAs specified by the command, update the volatile cache and/or non-volatile
	// cache to prevent retrieval of stale data.
	// since we don't cache blocks, just QCOW tables write cache, since it is expected.
	return backingStore.image.Flush()
}

func (backingStore *Qcow2BackingStore) Unmap() error {
	return nil
}

func (backingStore *Qcow2BackingStore) GetPath() string {
	if backingStore.image != nil {
		return backingStore.image.GetPath()
	}
	return ""
}
