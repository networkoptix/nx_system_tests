// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package scsi

import (
	"qcow2target/pkg/logger"
)

type BaseBackingStore struct {
	Name            string
	DataSize        uint64
	OflagsSupported int
}

type BackingStore interface {
	Open(path string) error
	Close() error
	Init() error
	Exit() error
	Size() uint64
	Read(offset, tl uint64) ([]byte, error)
	Write([]byte, uint64) error
	DataSync() error
	DataAdvise() error
	Unmap() error
	GetPath() string
}

type NullBackingStore struct {
	Name            string
	DataSize        uint64
	OflagsSupported int
}

func NewNull() (BackingStore, error) {
	return &NullBackingStore{
		Name:            "null",
		DataSize:        0,
		OflagsSupported: 0,
	}, nil
}

func (backingStore *NullBackingStore) Open(path string) error {
	log := logger.GetLogger()
	log.Debugf(
		"opened null backing store with path %s",
		path,
	)
	return nil
}

func (backingStore *NullBackingStore) Close() error {
	return nil
}

func (backingStore *NullBackingStore) Init() error {
	return nil
}

func (backingStore *NullBackingStore) Exit() error {
	return nil
}

func (backingStore *NullBackingStore) Size() uint64 {
	return 0
}

func (backingStore *NullBackingStore) Read(offset, transferLength uint64) ([]byte, error) {
	log := logger.GetLogger()
	log.Debugf(
		"Called READ on NullBackingStore with transfer length %d and offset %d",
		transferLength,
		offset,
	)
	return nil, nil
}

func (backingStore *NullBackingStore) Write(writeBuffer []byte, offset uint64) error {
	log := logger.GetLogger()
	log.Debugf(
		"Called READ on NullBackingStore with buffer size %d and offset %d",
		len(writeBuffer),
		offset,
	)
	return nil
}

func (backingStore *NullBackingStore) DataSync() error {
	return nil
}

func (backingStore *NullBackingStore) DataAdvise() error {
	return nil
}

func (backingStore *NullBackingStore) Unmap() error {
	return nil
}

func (backingStore *NullBackingStore) GetPath() string {
	return ""
}

func HandleRead(device *LogicalUnit, command *SCSICommand) *CommandError {
	readBuffer, err := device.BackingStorage.Read(command.Offset, uint64(command.TransferLength))
	if err != nil {
		return &CommandError{
			senseCode:           MediumError,
			additionalSenseCode: AscReadError,
		}
	}
	length := len(readBuffer)
	for i := 0; i < int(command.TransferLength)-length; i++ {
		readBuffer = append(readBuffer, 0)
	}
	command.InSDBBuffer.Residual = uint32(length)
	if command.InSDBBuffer.Length < uint32(length) {
		return &CommandError{
			senseCode:           IllegalRequest,
			additionalSenseCode: AscInvalidFieldInCdb,
		}
	}
	copy(command.InSDBBuffer.Buffer, readBuffer)
	return nil
}

func HandleWrite(device *LogicalUnit, command *SCSICommand) *CommandError {
	log := logger.GetLogger()
	var pg *ModePage
	err := device.BackingStorage.Write(command.OutSDBBuffer.Buffer, command.Offset)
	if err != nil {
		log.Error(err)
		return &CommandError{
			senseCode:           MediumError,
			additionalSenseCode: AscWriteError,
		}
	}
	log.Debugf(
		"write data at 0x%x for length %d",
		command.Offset,
		len(command.OutSDBBuffer.Buffer))
	for _, p := range device.ModePages {
		if p.PageCode == 0x08 && p.SubPageCode == 0 {
			pg = &p
			break
		}
	}
	if pg == nil {
		return &CommandError{
			senseCode:           IllegalRequest,
			additionalSenseCode: AscInvalidFieldInCdb,
		}
	}
	forceUnitAccessBitMask := byte(0x8)
	if (command.SCB[1]&forceUnitAccessBitMask != 0) || (pg.Data[0]&0x04 == 0) {
		if err = device.BackingStorage.DataSync(); err != nil {
			return &CommandError{
				senseCode:           MediumError,
				additionalSenseCode: AscWriteError,
			}
		}
	}
	return nil
}

func HandleSync(backingStore BackingStore) *CommandError {
	if err := backingStore.DataSync(); err != nil {
		return &CommandError{
			senseCode:           MediumError,
			additionalSenseCode: AscReadError,
		}
	}
	return nil
}

func HandleWriteSame(device *LogicalUnit, command *SCSICommand) *CommandError {
	transferLength := uint64(command.TransferLength)
	offset := command.Offset
	buffer := command.OutSDBBuffer
	blockSize := uint64(1 << device.BlockShift)
	if blockSize != uint64(buffer.Length) {
		return &CommandError{
			senseCode:           MediumError,
			additionalSenseCode: AscWriteError,
		}
	}
	// todo what if Transfer Length is zero by default
	for transferLength > 0 {
		err := device.BackingStorage.Write(command.OutSDBBuffer.Buffer, offset)
		if err != nil {
			return &CommandError{
				senseCode:           MediumError,
				additionalSenseCode: AscWriteError,
			}
		}
		transferLength -= blockSize
		offset += blockSize
	}
	return nil
}
