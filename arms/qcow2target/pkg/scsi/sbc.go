// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
// Package scsi block command processing
package scsi

import (
	"encoding/binary"
	"qcow2target/pkg/logger"
)

func SBCModeSelect() SAMStat {
	return SAMStatGood
}

// SBCFormatUnit Implements SCSI FORMAT UNIT command
// The FORMAT UNIT command requests that the device server format the medium into application client
// accessible logical blocks as specified in the number of blocks and block length values received
// in the last mode parameter block descriptor in a MODE SELECT command (see SPC-3).  In addition,
// the device server may certify the medium and create control structures for the management of the medium and defects.
// The degree that the medium is altered by this command is vendor-specific.
//
// Reference : SBC2r16
// 5.2 - FORMAT UNIT
func SBCFormatUnit(device *LogicalUnit, command *SCSICommand) SAMStat {
	formatProtectionInformationBitmask := byte(0x80)
	formatDataBitMask := byte(0x10)
	defectListBitMask := byte(0x07)
	// todo error for logical unit 0
	if err := device.Reserve(command); err != nil {
		return SAMStatReservationConflict
	}

	if !device.Attrs.Online {
		BuildSenseData(command, NotReady, AscMediumNotPresent)
		return SAMStatCheckCondition
	}

	if command.SCB[1]&formatProtectionInformationBitmask != 0 {
		// we dont support format protection information
		BuildSenseData(command, IllegalRequest, AscInvalidFieldInCdb)
		return SAMStatCheckCondition
	}
	if command.SCB[1]&formatDataBitMask != 0 {
		// we dont support format data
		BuildSenseData(command, IllegalRequest, AscInvalidFieldInCdb)
		return SAMStatCheckCondition
	}
	if command.SCB[1]&defectListBitMask != 0 {
		// defect list format must be 0
		BuildSenseData(command, IllegalRequest, AscInvalidFieldInCdb)
		return SAMStatCheckCondition
	}

	return SAMStatGood
}

func validateOffsetLength(transferLength, logicalBlockAddress, deviceSizeInBlocks uint64) bool {
	log := logger.GetLogger()
	if transferLength != 0 {
		// check for uint64 overflow of the end of the area
		logicalBlockAddressOverflow := logicalBlockAddress+transferLength < logicalBlockAddress
		if logicalBlockAddressOverflow || logicalBlockAddress+transferLength > deviceSizeInBlocks {
			log.Warnf(
				"sense data(ILLEGAL_REQUEST,ASC_LBA_OUT_OF_RANGE)"+
					" encounter: logicalBlockAddress: %d, tl: %d, size: %d",
				logicalBlockAddress,
				transferLength,
				deviceSizeInBlocks,
			)
			return false
		}
	} else {
		if logicalBlockAddress >= deviceSizeInBlocks {
			log.Warnf(
				"sense data(ILLEGAL_REQUEST,ASC_LBA_OUT_OF_RANGE)"+
					" encounter: logicalBlockAddress: %d, size: %d",
				logicalBlockAddress,
				deviceSizeInBlocks,
			)
			return false
		}
	}
	return true
}

func SBCRead(device *LogicalUnit, command *SCSICommand) SAMStat {
	log := logger.GetLogger()
	const readProtectBitMask = byte(0xe0)
	if command.SCB[1]&readProtectBitMask != 0 {
		BuildSenseData(command, IllegalRequest, AscInvalidFieldInCdb)
		log.Warnf("sense data(ILLEGAL_REQUEST,ASC_INVALID_FIELD_IN_CDB) encounter")
		return SAMStatCheckCondition
	}
	logicalBlockAddress := getSCSIReadWriteOffset(command.SCB)
	transferLength := getSCSIReadWriteCount(command.SCB)
	deviceSizeInBlocks := device.Size >> device.BlockShift
	ok := validateOffsetLength(uint64(transferLength), logicalBlockAddress, deviceSizeInBlocks)
	if !ok {
		BuildSenseData(command, IllegalRequest, AscLbaOutOfRange)
		log.Warnf("sense data(ILLEGAL_REQUEST,ASC_INVALID_FIELD_IN_CDB) encounter")
		return SAMStatCheckCondition
	}
	command.Offset = logicalBlockAddress << device.BlockShift
	command.TransferLength = transferLength << device.BlockShift
	scsiErr := HandleRead(device, command)
	if scsiErr != nil {
		BuildSenseData(command, scsiErr.senseCode, scsiErr.additionalSenseCode)
		return SAMStatBusy
	}
	return SAMStatGood
}

func SbcWrite(device *LogicalUnit, command *SCSICommand) SAMStat {
	log := logger.GetLogger()
	const writeProtectBitMask = byte(0xe0)
	if command.SCB[1]&writeProtectBitMask != 0 {
		BuildSenseData(command, IllegalRequest, AscInvalidFieldInCdb)
		log.Warnf("sense data(ILLEGAL_REQUEST,ASC_INVALID_FIELD_IN_CDB) encounter")
		return SAMStatCheckCondition
	}
	logicalBlockAddress := getSCSIReadWriteOffset(command.SCB)
	transferLength := getSCSIReadWriteCount(command.SCB)
	deviceSizeInBlocks := device.Size >> device.BlockShift
	ok := validateOffsetLength(uint64(transferLength), logicalBlockAddress, deviceSizeInBlocks)
	if !ok {
		BuildSenseData(command, IllegalRequest, AscLbaOutOfRange)
		log.Warnf("sense data(ILLEGAL_REQUEST,ASC_INVALID_FIELD_IN_CDB) encounter")
		return SAMStatCheckCondition
	}
	command.Offset = logicalBlockAddress << device.BlockShift
	command.TransferLength = transferLength << device.BlockShift
	scsiErr := HandleWrite(device, command)
	if scsiErr != nil {
		BuildSenseData(command, scsiErr.senseCode, scsiErr.additionalSenseCode)
		return SAMStatBusy
	}
	return SAMStatGood
}

func SbcWriteSame16(device *LogicalUnit, command *SCSICommand) SAMStat {
	log := logger.GetLogger()
	// We dont support resource-provisioning so ANCHOR bit == 1 is an error.
	const (
		anchorBitMask       = byte(0x10)
		unmapBitMask        = byte(0x08)
		writeProtectBitMask = byte(0xe0)
		lbDataBitMask       = byte(0x04)
		pbDataBitMask       = byte(0x02)
		obsoleteBitMask     = byte(0x06)
	)
	if command.SCB[1]&anchorBitMask != 0 {
		BuildSenseData(command, IllegalRequest, AscInvalidFieldInCdb)
		return SAMStatCheckCondition
	}
	// We only support unmap for thin provisioned LUNS
	if command.SCB[1]&unmapBitMask != 0 {
		BuildSenseData(command, IllegalRequest, AscInvalidFieldInCdb)
		return SAMStatCheckCondition
	}
	// We only support protection information type 0
	if command.SCB[1]&writeProtectBitMask != 0 {
		BuildSenseData(command, IllegalRequest, AscInvalidFieldInCdb)
		return SAMStatCheckCondition
	}
	// LBDATA and PBDATA can not both be set
	if (command.SCB[1] & obsoleteBitMask) == (lbDataBitMask | pbDataBitMask) {
		BuildSenseData(command, IllegalRequest, AscInvalidFieldInCdb)
		return SAMStatCheckCondition
	}
	logicalBlockAddress := getSCSIReadWriteOffset(command.SCB)
	transferLength := getSCSIReadWriteCount(command.SCB)
	deviceSizeInBlocks := device.Size >> device.BlockShift
	ok := validateOffsetLength(uint64(transferLength), logicalBlockAddress, deviceSizeInBlocks)
	if !ok {
		BuildSenseData(command, IllegalRequest, AscLbaOutOfRange)
		log.Warnf("sense data(ILLEGAL_REQUEST,ASC_INVALID_FIELD_IN_CDB) encounter")
		return SAMStatCheckCondition
	}
	command.Offset = logicalBlockAddress << device.BlockShift
	command.TransferLength = transferLength << device.BlockShift
	scsiErr := HandleWriteSame(device, command)
	if scsiErr != nil {
		BuildSenseData(command, scsiErr.senseCode, scsiErr.additionalSenseCode)
		return SAMStatBusy
	}
	return SAMStatGood
}

// SBCReadCapacity Implements SCSI READ CAPACITY(10) command
// The READ CAPACITY (10) command requests that the device server transfer 8 bytes of parameter data
// describing the capacity and medium format of the direct-access block device to the data-in buffer.
// This command may be processed as if it has a HEAD OF QUEUE task attribute.  If the logical unit supports
// protection information, the application client should use the READ CAPACITY (16) command instead of
// the READ CAPACITY (10) command.
//
// Reference : SBC2r16
// 5.10 - READ CAPACITY(10)
func SBCReadCapacity(device *LogicalUnit, command *SCSICommand) SAMStat {
	size := device.Size >> device.BlockShift

	if (command.SCB[8]&0x1 == 0) && (command.SCB[2]|command.SCB[3]|command.SCB[4]|command.SCB[5]) != 0 {
		if command.InSDBBuffer != nil {
			command.InSDBBuffer.Residual = 0
		}
		BuildSenseData(command, IllegalRequest, AscInvalidFieldInCdb)
		return SAMStatCheckCondition
	}

	if command.InSDBBuffer.Length < 8 {
		command.InSDBBuffer.Residual = 8
		return SAMStatGood
	}

	if size>>32 != 0 {
		copy(command.InSDBBuffer.Buffer, MarshalUint32(uint32(0xffffffff)))
	} else {
		copy(command.InSDBBuffer.Buffer, MarshalUint32(uint32(size-1)))
	}
	copy(command.InSDBBuffer.Buffer[4:], MarshalUint32(uint32(1<<device.BlockShift)))
	return SAMStatGood
}

// SBCReadCapacity16 Implements SCSI READ CAPACITY(16) command
// The READ CAPACITY (16) command requests that the device server transfer parameter data
// describing the capacity and medium format of the direct-access block device to the data-in buffer.
//
// Reference : SBC2r16
// 5.11 - READ CAPACITY(16)
func SBCReadCapacity16(device *LogicalUnit, command *SCSICommand) SAMStat {
	size := device.Size >> device.BlockShift
	allocationLength := binary.BigEndian.Uint32(command.SCB[10:14])
	copy(command.InSDBBuffer.Buffer, MarshalUint64(size-1))
	if allocationLength > 12 {
		copy(command.InSDBBuffer.Buffer[8:], MarshalUint32(uint32(1<<device.BlockShift)))
		if allocationLength > 16 {
			val := (device.Attrs.LogicalBlocksPerPhysicalBlockExponent << 16) | device.Attrs.LowestAlignedLBA
			copy(command.InSDBBuffer.Buffer[12:], MarshalUint32(uint32(val)))
		}
	}
	return SAMStatGood
}

// SbcSyncCache Implements SCSI SYNCHRONIZE CACHE(16) command
// The SYNCHRONIZE CACHE command requests that the device server ensure that
// the specified logical blocks have their most recent data values recorded in
// non-volatile cache and/or on the medium, based on the SYNC_NV bit.
//
// Reference : SBC2r16
// 5.19 - SYNCHRONIZE CACHE (16)
func SbcSyncCache(device *LogicalUnit, command *SCSICommand) SAMStat {
	logicalBlockAddress := getSCSIReadWriteOffset(command.SCB)
	numberOfLogicalBlock := getSCSIReadWriteCount(command.SCB)
	command.Offset = logicalBlockAddress << device.BlockShift
	command.TransferLength = numberOfLogicalBlock << device.BlockShift

	err := HandleSync(device.BackingStorage)
	if err != nil {
		BuildSenseData(command, err.senseCode, err.additionalSenseCode)
		return SAMStatCheckCondition
	}
	return SAMStatGood
}

func SBCStartStop(device *LogicalUnit, command *SCSICommand) SAMStat {
	// todo error for logical unit 0
	if err := device.Reserve(command); err != nil {
		return SAMStatReservationConflict
	}

	if command.InSDBBuffer != nil {
		command.InSDBBuffer.Residual = 0
	}
	return SAMStatGood
}
