// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
// Package scsi
// SCSI primary command processing
package scsi

import (
	"encoding/binary"
	"qcow2target/pkg/logger"
)

// SPCReportLuns Implements SCSI REPORT LUNS command
// The REPORT LUNS command requests the device server to return the peripheral Device
// logical unit inventory accessible to the I_T nexus.
//
// Reference : SPC4r11
// 6.33 - REPORT LUNS
func SPCReportLuns(command *SCSICommand) SAMStat {
	log := logger.GetLogger()
	// Get Allocation Length
	allocationLength := binary.BigEndian.Uint32(command.SCB[6:10])
	if allocationLength < 16 {
		log.Warn("Invalid allocation length, must be > 16")
		if command.InSDBBuffer != nil {
			command.InSDBBuffer.Residual = 0
		}
		BuildSenseData(command, IllegalRequest, AscInvalidFieldInCdb)
		return SAMStatCheckCondition
	}

	remainingLength := allocationLength
	availableLength := uint16(len(command.Target.Devices) * 8)
	if _, ok := command.Target.Devices[0]; !ok {
		availableLength += 8
	}
	response := []byte{
		// 32 bit length of all LUNs
		// (8 byte for each LUN, maximum 255 LUNs, so fits into uint16),
		// big endian.
		0x00, 0x00, byte(availableLength >> 8), byte(availableLength),
		// Reserved
		0x00, 0x00, 0x00, 0x00,
	}
	command.InSDBBuffer.Residual = allocationLength

	//For LUN0
	if _, ok := command.Target.Devices[0]; !ok {
		response = append(response, 0x00, 0x00, 0x00, 0x00)
		remainingLength -= 8
	}

	for lun := range command.Target.Devices {
		if remainingLength <= 0 {
			break
		}
		response = append(
			response,
			// first byte is ADDRESS METHOD and BUS IDENTIFIER
			// ADDRESS METHOD - single level logical unit LUN number structure
			// BUS IDENTIFIER - 0
			0x00,
			lun,        // single level LUN
			0x00, 0x00, // NULL second level LUN
			0x00, 0x00, // NULL third level LUN
			0x00, 0x00, // NULL fourth level LUN
		)
		remainingLength -= 8
	}
	copy(command.InSDBBuffer.Buffer, response)
	return SAMStatGood
}

//SPCTestUnit Implements SCSI TEST UNIT READY command
//The TEST UNIT READY command requests the device server to indicate whether the logical unit is ready.//Reference : SPC4r11
//6.47 - TEST UNIT READY
func SPCTestUnit(device *LogicalUnit, command *SCSICommand) SAMStat {
	if device.Attrs.Online {
		return SAMStatGood
	}
	BuildSenseData(command, NotReady, AscBecomingReady)
	return SAMStatCheckCondition
}

//SPCModeSense10 Implement SCSI MODE SENSE(10)
//The MODE SENSE command requests the device server to return the specified medium,
//logical unit, or peripheral device parameters.//Reference : SPC5r19
//6.15 - MODE SENSE(10)
func SPCModeSense10(device *LogicalUnit, command *SCSICommand) SAMStat {
	log := logger.GetLogger()
	disableBlockDescriptorsBitMask := byte(0x8)
	// first six bit of second request byte
	pageCodeBitMask := byte(0x3f)
	// last two bits of second request byte
	pageControlBitMask := byte(0xc0)
	disableBlockDescriptors := command.SCB[1] & disableBlockDescriptorsBitMask
	pageCode := command.SCB[2] & pageCodeBitMask
	pageControl := (command.SCB[2] & pageControlBitMask) >> 6
	subPageCode := command.SCB[3]
	allocationLength := binary.BigEndian.Uint32(command.SCB[7:9])

	if pageControl == 3 {
		BuildSenseData(command, IllegalRequest, AscSavingParmsUnsup)
		return SAMStatCheckCondition
	}
	blockDescriptorLength := byte(0)
	blockDescriptor := make([]byte, 0, 8)
	if disableBlockDescriptors == 0 {
		blockDescriptorLength = byte(8)
		blockDescriptor = append(blockDescriptor, device.ModeBlockDescriptor...)
	}
	modeParameterListData, err := device.ModePages.toBytes(
		pageCode, subPageCode, pageControl)
	if err != nil {
		log.Error(err)
		BuildSenseData(command, IllegalRequest, AscInvalidFieldInCdb)
		return SAMStatCheckCondition
	}
	listDataLength := len(modeParameterListData)
	responseData := []byte{
		// MODE DATA LENGTH field indicates the number of bytes that
		// follow in the mode parameter list.
		byte(listDataLength >> 8), byte(listDataLength),
		// MEDIUM TYPE (Data-medium)
		0x00,
		// DEVICE -SPECIFIC PARAMETER
		// We implement only block devices
		// DPOFUA bit (bitmask 0x10) is set
		// DPOFUA means DPO and FUA support,
		// DPO means disable page out
		// (it sets ability to override retention priority with caches)
		// we don't use caches.
		// FUA - force unit access,
		// specifies from where do we read data
		// (unmapped lbas, cache or medium)
		// we don't use cache and do not implement unmap,
		// so always read from medium.
		// Write protect bit (mask 0x80) is not set
		0x10,
		// Reserved
		0x00,
		0x00,
		// BLOCK DESCRIPTOR LENGTH
		0x00, blockDescriptorLength,
	}
	responseData = append(responseData, blockDescriptor...)
	responseData = append(responseData, modeParameterListData...)

	if pagesLength := uint32(len(responseData)); pagesLength > allocationLength {
		command.InSDBBuffer.Residual = allocationLength
	}
	copy(command.InSDBBuffer.Buffer, responseData)
	return SAMStatGood
}

//SPCModeSense6 Implement SCSI MODE SENSE(6)
// The MODE SENSE command requests the device server to return the specified medium,
// logical unit, or peripheral device parameters.
// Reference : SPC5r19
//6.14 - MODE SENSE(6)
func SPCModeSense6(device *LogicalUnit, command *SCSICommand) SAMStat {
	log := logger.GetLogger()
	disableBlockDescriptorsBitMask := byte(0x8)
	// first six bit of second request byte
	pageCodeBitMask := byte(0x3f)
	// last two bits of second request byte
	pageControlBitMask := byte(0xc0)
	disableBlockDescriptors := command.SCB[1] & disableBlockDescriptorsBitMask
	pageCode := command.SCB[2] & pageCodeBitMask
	pageControl := (command.SCB[2] & pageControlBitMask) >> 6
	subPageCode := command.SCB[3]
	allocationLength := uint32(command.SCB[4])

	if pageControl == 3 {
		BuildSenseData(command, IllegalRequest, AscSavingParmsUnsup)
		return SAMStatCheckCondition
	}

	blockDescriptorLength := byte(0)
	blockDescriptor := make([]byte, 0, 8)
	if disableBlockDescriptors == 0 {
		blockDescriptorLength = byte(8)
		blockDescriptor = append(blockDescriptor, device.ModeBlockDescriptor...)
	}
	modeParameterListData, err := device.ModePages.toBytes(
		pageCode, subPageCode, pageControl)
	if err != nil {
		log.Error(err)
		BuildSenseData(command, IllegalRequest, AscInvalidFieldInCdb)
		return SAMStatCheckCondition
	}
	responseData := []byte{
		// MODE DATA LENGTH field indicates the number of bytes that
		// follow in the mode parameter list.
		byte(len(modeParameterListData)),
		// MEDIUM TYPE (Data-medium)
		0x00,
		// We implement only block devices
		// DPOFUA bit (bitmask 0x10) is set
		// DPOFUA means DPO and FUA support,
		// DPO means disable page out
		// (it sets ability to override retention priority with caches)
		// we don't use caches.
		// FUA - force unit access,
		// specifies from where do we read data
		// (unmapped lbas, cache or medium)
		// we don't use cache and do not implement unmap,
		// so always read from medium.
		// Write protect bit (mask 0x80) is not set
		0x10,
		// BLOCK DESCRIPTOR LENGTH
		blockDescriptorLength,
	}
	responseData = append(responseData, blockDescriptor...)
	responseData = append(responseData, modeParameterListData...)

	if pagesLength := uint32(len(responseData)); pagesLength > allocationLength {
		command.InSDBBuffer.Residual = allocationLength
	}
	copy(command.InSDBBuffer.Buffer, responseData)
	return SAMStatGood

}

// SPCRequestSense Implements SCSI REQUEST SENSE command
// The REQUEST SENSE command requests the device server to
// return parameter data that contains sense data.
// Reference : SPC4r11
// 6.39 - REQUEST SENSE
func SPCRequestSense(command *SCSICommand) SAMStat {
	actualLength := uint32(0)
	allocationLength := uint32(command.SCB[4])
	if allocationLength > command.InSDBBuffer.Length {
		allocationLength = command.InSDBBuffer.Length
	}
	BuildSenseData(command, NoSense, NoAdditionalSense)
	if command.SenseBuffer.Length < allocationLength {
		actualLength = command.SenseBuffer.Length
	} else {
		actualLength = allocationLength
	}
	copy(command.InSDBBuffer.Buffer, command.SenseBuffer.Buffer[:actualLength])
	command.InSDBBuffer.Residual = actualLength

	// reset sense buffer in command
	command.SenseBuffer = &SenseBuffer{}

	return SAMStatGood
}
