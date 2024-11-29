// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package scsi

import (
	"bytes"
	"encoding/binary"
	"fmt"
	"qcow2target/pkg/logger"
	"qcow2target/pkg/qcow2"
	"sync"
)

type TargetService struct {
	mutex        sync.RWMutex
	targets      []*SCSITarget
	targetByName map[string]*SCSITarget
	targetByTid  map[int]*SCSITarget
	LunFactory   LogicalUnitFactory
}

func NewSCSITargetService(imageFactory *qcow2.ImageFactory) *TargetService {
	return &TargetService{
		mutex:        sync.RWMutex{},
		targets:      []*SCSITarget{},
		targetByName: make(map[string]*SCSITarget),
		targetByTid:  make(map[int]*SCSITarget),
		LunFactory:   newLogicalUnitFactory(imageFactory),
	}
}

func (targetService *TargetService) getTargetByTid(targetId int) (*SCSITarget, bool) {
	targetService.mutex.RLock()
	target, ok := targetService.targetByTid[targetId]
	targetService.mutex.RUnlock()
	if !ok {
		return nil, false
	}
	return target, true
}

func (targetService *TargetService) AddCommandQueue(targetId int, scsiCommand *SCSICommand) error {
	log := logger.GetLogger()
	target, ok := targetService.getTargetByTid(targetId)
	if !ok {
		return fmt.Errorf("cannot find the target with ID(%d)", targetId)
	}
	scsiCommand.Target = target
	scsiCommand.ITNexus = target.GetItNexus(scsiCommand)
	device := target.Devices[scsiCommand.LogicalUnit]

	log.Debugf(
		"scsi opcode: %s, LUN: %d",
		OperationCodeToString(CommandType(scsiCommand.OperationCode)),
		scsiCommand.LogicalUnit,
	)
	if device == nil {
		device = target.LUN0
		if scsiCommand.LogicalUnit != 0 {
			BuildSenseData(scsiCommand, IllegalRequest, AscInvalidFieldInCdb)
			scsiCommand.Result = SAMStatCheckCondition.Stat
			log.Warnf("%v", SAMStatCheckCondition.Err)
			return nil
		}
	}

	result := device.PerformCommand(scsiCommand)
	if result != SAMStatGood {
		scsiCommand.Result = result.Stat
		log.Warnf("opcode: %xh err: %v", scsiCommand.OperationCode, result.Err)
	}
	return nil
}

func BuildSenseData(command *SCSICommand, key byte, asc AdditionalSenseCode) {
	senseBuffer := &bytes.Buffer{}
	length := uint32(0xa)
	// fixed format
	// current, not deferred
	senseBuffer.WriteByte(0x70)
	senseBuffer.WriteByte(0x00)
	senseBuffer.WriteByte(key)
	for i := 0; i < 4; i++ {
		senseBuffer.WriteByte(0x00)
	}
	senseBuffer.WriteByte(byte(length))
	for i := 0; i < 4; i++ {
		senseBuffer.WriteByte(0x00)
	}
	senseBuffer.WriteByte(byte(asc>>8) & 0xff)
	senseBuffer.WriteByte(byte(asc) & 0xff)
	for i := 0; i < 4; i++ {
		senseBuffer.WriteByte(0x00)
	}
	length += 8
	command.Result = key
	command.SenseBuffer = &SenseBuffer{senseBuffer.Bytes(), length}
}

func getSCSIReadWriteOffset(scb []byte) uint64 {
	switch CommandType(scb[0]) {
	case Read10, Write10, SynchronizeCache10:
		return uint64(binary.BigEndian.Uint32(scb[2:]))
	case Read16, Write16, WriteSame16, SynchronizeCache16:
		return binary.BigEndian.Uint64(scb[2:])
	default:
		return uint64(0)
	}
}

func getSCSIReadWriteCount(scb []byte) uint32 {
	switch CommandType(scb[0]) {
	case Read10, Write10, SynchronizeCache10:
		return uint32(binary.BigEndian.Uint16(scb[7:]))
	case Read16, Write16, WriteSame16, SynchronizeCache16:
		return binary.BigEndian.Uint32(scb[10:])
	default:
		return uint32(0)
	}
}
