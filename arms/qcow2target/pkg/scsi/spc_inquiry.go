// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package scsi

import (
	"encoding/binary"
	"fmt"
)

/*
 * Protocol Identifier Values
 *
 * 0 Fibre Channel (FCP-2)
 * 1 Parallel SCSI (SPI-5)
 * 2 SSA (SSA-S3P)
 * 3 IEEE 1394 (SBP-3)
 * 4 SCSI Remote Direct Memory Access (SRP)
 * 5 iSCSI
 * 6 SAS Serial SCSI Protocol (SAS)
 * 7 Automation/Drive Interface (ADT)
 * 8 AT Attachment Interface (ATA/ATAPI-7)
 */

const (
	ProtocolIdentifierValueIscsi = byte(0x05)
)

const (
	VersionWithdrawSpc3 = byte(0x05)
)

/*
 * Code Set
 *
 *  1 - Designator fild contains binary values
 *  2 - Designator field contains ASCII printable chars
 *  3 - Designaotor field contains UTF-8
 */
const (
	InqCodeBin   = byte(1)
	InqCodeAscii = byte(2)
	InqCodeUtf8  = byte(3)
)

/*
 * Association field
 *
 * 00b - Associated with Logical Unit
 * 01b - Associated with target port
 * 10b - Associated with SCSI Target device
 * 11b - Reserved
 */
const (
	AssociatedLogicalUnit = byte(0x00)
	AssociatedTgtPort     = byte(0x01)
)

/*
 * Table 177 — PERIPHERAL QUALIFIER field
 * Qualifier Description
 * 000b - A peripheral device having the indicated peripheral
 * 	device type is connected to this logical unit. If the device server is
 * 	unable to determine whether or not a peripheral device is connected,
 * 	then the device server also shall use this peripheral qualifier.
 * 	This peripheral qualifier does not indicate that the peripheral
 * 	device connected to the logical unit is ready for access.
 * 001b - A peripheral device having the indicated peripheral device type
 * 	is not connected to this logical unit. However, the device server is capable of
 *	supporting the indicated peripheral device type on this logical unit.
 * 010b - Reserved
 * 011b - The device server is not capable of supporting a
 * 	peripheral device on this logical unit. For this peripheral
 *	qualifier the peripheral device type shall be set to 1Fh. All other peripheral
 * device type values are reserved for this peripheral qualifier.
 * 100b to 111b Vendor specific
 */
const (
	PeripheralQualifierDeviceConnected  = byte(0x00)
	PeripheralQualifierDeviceNotConnect = byte(0x01 << 5)
)

const (
	InquiryTpgsImplicit   = byte(0x10)
	InquiryHisup          = byte(0x10)
	InquiryStandardFormat = byte(0x02)
	InquiryCmdque         = byte(0x02)
)

/*
 * Designator type - SPC-4 Reference
 *
 * 0 - Vendor specific - 7.6.3.3
 * 1 - T10 vendor ID - 7.6.3.4
 * 2 - EUI-64 - 7.6.3.5
 * 3 - NAA - 7.6.3.6
 * 4 - Relative Target port identifier - 7.6.3.7
 * 5 - Target Port group - 7.6.3.8
 * 6 - Logical Unit group - 7.6.3.9
 * 7 - MD5 logical unit identifier - 7.6.3.10
 * 8 - SCSI name string - 7.6.3.11
 */
const (
	DesignatorTypeVendor     = 0
	DesignatorTypeNaa        = 3
	DesignatorTypeRelTgtPort = 4
	DesignatorTypeTgtPortGrp = 5
	DesignatorTypeScsi       = 8
)

const (
	NaaLocal = uint64(0x3)
)

const (
	supportedVpdPagesVpdPageCode          = byte(0x00)
	unitSerialNumberVpdPageCode           = byte(0x80)
	deviceIdentificationVpdPageCode       = byte(0x83)
	blockLimitsVpdPageCode                = byte(0xB0)
	blockDeviceCharacteristicsVpdPageCode = byte(0xB1)
	blockProvisioningVpdPageCode          = byte(0xB2)
)

func allVpdPagesCommonFirstByte(device *LogicalUnit) byte {
	peripheralQualifier := PeripheralQualifierDeviceConnected
	peripheralDeviceType := byte(device.Attrs.DeviceType)
	if !device.Attrs.Online {
		peripheralQualifier = PeripheralQualifierDeviceNotConnect
	}
	return peripheralQualifier | peripheralDeviceType
}

func supportedVpdPagesVpdPage(device *LogicalUnit) []byte {
	pageLength := byte(0x06)
	return []byte{
		allVpdPagesCommonFirstByte(device),
		supportedVpdPagesVpdPageCode,
		0x00, pageLength, // page length in big endian
		supportedVpdPagesVpdPageCode,
		unitSerialNumberVpdPageCode,
		deviceIdentificationVpdPageCode,
		blockLimitsVpdPageCode,
		blockProvisioningVpdPageCode,
		blockDeviceCharacteristicsVpdPageCode,
	}
}

func unitSerialNumberVpdPage(device *LogicalUnit) []byte {
	pageLength := byte(0x24)
	scsiSerialNumber := []byte(
		fmt.Sprintf("qcow2target-%-36v", device.UUID))
	result := []byte{
		allVpdPagesCommonFirstByte(device),
		unitSerialNumberVpdPageCode,
		0x00, pageLength, // page length 2 bytes big endian
	}
	return append(result, scsiSerialNumber...)
}

func blockDeviceCharacteristicsVpdPage(device *LogicalUnit) []byte {
	return []byte{
		allVpdPagesCommonFirstByte(device),
		blockDeviceCharacteristicsVpdPageCode,
		// page length
		0x00, 0x3c,
		// medium rotation rate
		// 0001 - Non-rotating medium (e.g., solid state)
		0x00, 0x01,
		// Product type - not specified
		0x00,
		// WABEREQ, WACEREQ and Nominal form factor
		// WABEREQ - write after block eraze required
		// WACEREQ - write after cryptographic erase required
		// All not supported/reported
		0x00,
		// ZONED, RBWZ, BOCS, FUAB, VBULS
		// ZONED - indicates zoned device block capabilities
		// RBWZ - reassign blocks write zero,
		// not supported since we do not support REASSIGN BLOCKS command
		// BOCS - background operation control supported
		// FUAB force unit access behavior -
		// indicates that device interprets FUA in complience with SBC-4
		// if zero - SBC-2 (for SYNCHRONIZE CACHE)
		// VBULS - verify byte check unmapped LBA supported
		// also set to zero since we don't support unmap operation.
		0x00,
		// Reserved
		0x00, 0x00, 0x00,
		// DEPOPULATION TIME set to zero
		0x00, 0x00, 0x00, 0x00,
		// RESERVED
		0x00, 0x00, 0x00, 0x00,
		0x00, 0x00, 0x00, 0x00,
		0x00, 0x00, 0x00, 0x00,
		0x00, 0x00, 0x00, 0x00,
		0x00, 0x00, 0x00, 0x00,
		0x00, 0x00, 0x00, 0x00,
		0x00, 0x00, 0x00, 0x00,
		0x00, 0x00, 0x00, 0x00,
		0x00, 0x00, 0x00, 0x00,
		0x00, 0x00, 0x00, 0x00,
		0x00, 0x00, 0x00, 0x00,
		0x00, 0x00, 0x00, 0x00,
	}
}

func protocolIdentifierAndCodeSet(codeSet byte) byte {
	return (ProtocolIdentifierValueIscsi << 4) | codeSet
}

func associationAndDesignatorType(association, designatorType byte) byte {
	protocolIdentifierValueBitmask := byte(0x80)
	return protocolIdentifierValueBitmask | (association << 4) | designatorType
}

func deviceIdentificationVpdPage(device *LogicalUnit, command *SCSICommand) []byte {
	result := []byte{
		allVpdPagesCommonFirstByte(device),
		deviceIdentificationVpdPageCode,
	}
	targetName := []byte(command.Target.Name)
	targetNameDescriptorLength := byte(len(targetName))
	targetNameDescriptor := []byte{
		protocolIdentifierAndCodeSet(InqCodeAscii),
		associationAndDesignatorType(AssociatedTgtPort, DesignatorTypeVendor),
		targetNameDescriptorLength,
	}
	targetNameDescriptor = append(targetNameDescriptor, targetName...)
	networkAddressAuthorityDescriptor := []byte{
		protocolIdentifierAndCodeSet(InqCodeBin),
		associationAndDesignatorType(AssociatedLogicalUnit, DesignatorTypeNaa),
		0x00, 0x08, // length 16 bit big endian
		// NAA local is 8 byte
	}
	networkAddressAuthorityLocalBitmask := uint64(60)
	networkAddressAuthority := MarshalUint64(
		device.UUID | (NaaLocal << networkAddressAuthorityLocalBitmask),
	)
	networkAddressAuthorityDescriptor = append(
		networkAddressAuthorityDescriptor, networkAddressAuthority...)
	targetPortGroupDescriptor := []byte{
		protocolIdentifierAndCodeSet(InqCodeBin),
		associationAndDesignatorType(AssociatedTgtPort, DesignatorTypeTgtPortGrp),
		0x00, 0x04, // length
		0x00, 0x00,
		byte(command.TargetPortGroupId >> 8), // uint16 big
		byte(command.TargetPortGroupId),
	}
	relativeTargetIdDescriptor := []byte{
		protocolIdentifierAndCodeSet(InqCodeBin),
		associationAndDesignatorType(AssociatedTgtPort, DesignatorTypeRelTgtPort),
		0x00, 0x04, // length
		0x00, 0x00,
		byte(command.RelTargetPortID >> 8), // uint16 big
		byte(command.RelTargetPortID),
	}
	portName := StringToByte(command.TargetPortName, 4, 256)
	scsiNameDescriptor := []byte{
		protocolIdentifierAndCodeSet(InqCodeUtf8),
		associationAndDesignatorType(AssociatedTgtPort, DesignatorTypeScsi),
		0x00, byte(len(portName)),
	}
	scsiNameDescriptor = append(scsiNameDescriptor, portName...)
	pageLength := uint16(
		len(targetNameDescriptor) +
			len(networkAddressAuthorityDescriptor) +
			len(targetPortGroupDescriptor) +
			len(relativeTargetIdDescriptor) +
			len(scsiNameDescriptor),
	)
	result = append(
		result,
		byte(pageLength>>8),
		byte(pageLength),
	)
	result = append(result, targetNameDescriptor...)
	result = append(result, networkAddressAuthorityDescriptor...)
	result = append(result, targetPortGroupDescriptor...)
	result = append(result, relativeTargetIdDescriptor...)
	result = append(result, scsiNameDescriptor...)
	return result
}

func blockLimitsVpdPage(device *LogicalUnit) []byte {
	return []byte{
		allVpdPagesCommonFirstByte(device),
		blockLimitsVpdPageCode,
		0x00, 0x3C, // length 16 bit
		0x00, 0x00, 0x00, 0x00, // 16 byte padding
		0x00, 0x00, 0x00, 0x00,
		0x00, 0x00, 0x00, 0x00,
		0x00, 0x00, 0x00, 0x00,
		0x00, 0x00, 0x00, 0x00, // max unmap LBA count
		0x00, 0x00, 0x00, 0x00, // max unmap block descriptor count
		0x00, 0x00, 0x00, 0x00, // 36 byte padding
		0x00, 0x00, 0x00, 0x00,
		0x00, 0x00, 0x00, 0x00,
		0x00, 0x00, 0x00, 0x00,
		0x00, 0x00, 0x00, 0x00,
		0x00, 0x00, 0x00, 0x00,
		0x00, 0x00, 0x00, 0x00,
		0x00, 0x00, 0x00, 0x00,
		0x00, 0x00, 0x00, 0x00,
	}
}

func blockProvisioningVpdPage(device *LogicalUnit) []byte {
	return []byte{
		allVpdPagesCommonFirstByte(device),
		blockLimitsVpdPageCode,
		0x00, 0x04, //page length
		0x00, // threshold exponent
		0x00, // LBPU | LBPWS | LBPWS10 | LBPRZ | ANC_SUP | DP
		0x00, // MINIMUM PERCENTAGE | PROVISIONING TYPE
		0x00,
	}
}

func standardInquiryData(device *LogicalUnit) []byte {
	variadicLengthInquiryData := []byte{
		//starting from the 5-th byte
		// SCCS(0) obsolete TPGS(0) 3PC(0) PROTECT(0)
		// SCCS - Scsi controller commands supported bit
		// indicates that the SCSI target device contains an embedded storage
		// array controller component that is addressable through this logical unit
		// TPGS - target port group support - indicates
		// the support for asymmetric logical unit
		// 3PC - support for third party copy commands
		// PROTECT bit indicates protection type
		InquiryTpgsImplicit,
		//ENCSERV(0) VS(0) MULTIP(0) Obsolete
		// ENCSERV - Enclosure Services
		// indicates that the SCSI target device contains an embedded
		// enclosure services component that is addressable
		// through this logical unit
		// MULTIP indicates that target has multiple target ports
		0x00,
		// CMDQUE(1)
		// bit indicating whether device supports SAM 5 or not
		InquiryCmdque,
	}
	// 8 bytes of left aligned ASCII
	t10VendorIdentification := []byte(fmt.Sprintf("%-8s", device.Attrs.VendorID))
	variadicLengthInquiryData = append(variadicLengthInquiryData, t10VendorIdentification...)
	productIdentification := []byte(fmt.Sprintf("%-16s", device.Attrs.ProductID))
	variadicLengthInquiryData = append(variadicLengthInquiryData, productIdentification...)
	productRevision := []byte(fmt.Sprintf("%-4s", device.Attrs.ProductRev))
	variadicLengthInquiryData = append(variadicLengthInquiryData, productRevision...)
	variadicLengthInquiryData = append(
		variadicLengthInquiryData,
		0x00, 0x00, 0x00, 0x00, // 20 byte vendor specific
		0x00, 0x00, 0x00, 0x00,
		0x00, 0x00, 0x00, 0x00,
		0x00, 0x00, 0x00, 0x00,
		0x00, 0x00, 0x00, 0x00,
		0x00, 0x00, // 2 byte reserved and obsolete
	)
	variadicLengthInquiryData = append(
		variadicLengthInquiryData,
		device.Attrs.VersionDescription[:]...,
	)
	result := []byte{
		allVpdPagesCommonFirstByte(device),
		// Removable Media Bit (RMB = 0)
		//  Logical Unit Conglomerate(LU_CONG = 0)
		0x00,
		// Version
		VersionWithdrawSpc3,
		// Reserved, Reserved, NORMACA, HISUP, RESPONSE DATA FORMAT
		// NORMACA - Normal Auto Contingent Allegiance,
		// HISUP - (historical support) bit set to zero indicates the
		// SCSI target device does not use the LUN structures
		// described in SAM-5.
		InquiryHisup | InquiryStandardFormat,
		byte(len(variadicLengthInquiryData)),
	}
	result = append(result, variadicLengthInquiryData...)
	return result
}

//SPCInquiry Implements SCSI Inquiry command
//The Inquiry command requests the device server to return information
//regarding the logical unit and SCSI target device.
//Reference : SPC4r11
//6.6 - Inquiry
func SPCInquiry(device *LogicalUnit, command *SCSICommand) SAMStat {
	data := make([]byte, 0, 100)
	enableVitalProductDataBitmask := byte(0x01)
	enableVitalProductData := false
	pageCode := command.SCB[2]
	allocationLength := binary.BigEndian.Uint16(command.SCB[3:5])

	if command.SCB[1]&enableVitalProductDataBitmask > 0 {
		enableVitalProductData = true
	}

	if device == nil {
		BuildSenseData(command, IllegalRequest, AscInvalidFieldInCdb)
		return SAMStatCheckCondition
	}

	if enableVitalProductData {
		switch pageCode {
		case supportedVpdPagesVpdPageCode:
			data = supportedVpdPagesVpdPage(device)
		case unitSerialNumberVpdPageCode:
			data = unitSerialNumberVpdPage(device)
		case deviceIdentificationVpdPageCode:
			data = deviceIdentificationVpdPage(device, command)
		case blockLimitsVpdPageCode:
			data = blockLimitsVpdPage(device)
		case blockProvisioningVpdPageCode:
			data = blockProvisioningVpdPage(device)
		case blockDeviceCharacteristicsVpdPageCode:
			data = blockDeviceCharacteristicsVpdPage(device)
		default:
			BuildSenseData(command, IllegalRequest, AscInvalidFieldInCdb)
			return SAMStatCheckCondition
		}
		if int(allocationLength) < len(data) {
			copy(command.InSDBBuffer.Buffer, data[0:allocationLength])
			command.InSDBBuffer.Residual = uint32(len(data))
		} else {
			copy(command.InSDBBuffer.Buffer, data[0:])
		}
	} else {
		if pageCode != 0 {
			BuildSenseData(command, IllegalRequest, AscInvalidFieldInCdb)
			return SAMStatCheckCondition
		}
		data = standardInquiryData(device)
		additionLength := len(data) - 5 // 5 is length of the constant part
		if allocationLength < uint16(additionLength) {
			command.InSDBBuffer.Residual = uint32(allocationLength)
			copy(command.InSDBBuffer.Buffer, data[0:allocationLength])
		} else {
			command.InSDBBuffer.Residual = uint32(len(data))
			copy(command.InSDBBuffer.Buffer, data[0:])
		}
	}
	return SAMStatGood
}
