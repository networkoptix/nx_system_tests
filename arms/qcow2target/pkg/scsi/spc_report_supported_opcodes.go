// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package scsi

import (
	"qcow2target/pkg/logger"
)

const reportAllReportingOption = byte(0x00)
const reportSingleReportingOption = byte(0x01)
const reportSingleServiceActionReportingOption = byte(0x02)
const reportSingleReporingOptionAllowBoth = byte(0x03)

var timeoutsDescriptor = []byte{
	// Descriptor length
	0x00, 0x0a,
	// Reserved
	0x00,
	// Command specific
	0x00,
	// Nominal command processing timeout
	0x00, 0x00, 0x00, 0x00,
	// Recommended command timeout
	0x00, 0x00, 0x00, 0x00,
}

type commandDescription struct {
	hasServiceAction bool
	content          []byte
}

func (description commandDescription) length() byte {
	return byte(len(description.content))
}

var commandDescriptions = map[CommandType]map[byte]commandDescription{
	FormatUnit:         {0x00: {false, formatUnitUsage()}},
	Inquiry:            {0x00: {false, inquiryUsage()}},
	ModeSelect10:       {0x00: {false, modeSelect10Usage()}},
	ModeSense6:         {0x00: {false, modeSense6Usage()}},
	ModeSense10:        {0x00: {false, modeSense10Usage()}},
	Read10:             {0x00: {false, read10Usage()}},
	Read16:             {0x00: {false, read16Usage()}},
	ReportLuns:         {0x00: {false, reportLunsUsage()}},
	RequestSense:       {0x00: {false, requestSenseUsage()}},
	StartStop:          {0x00: {false, startStopUsage()}},
	SynchronizeCache10: {0x00: {false, synchronizeCache10Usage()}},
	SynchronizeCache16: {0x00: {false, synchronizeCache16Usage()}},
	TestUnitReady:      {0x00: {false, testUnitReadyUsage()}},
	Write10:            {0x00: {false, write10Usage()}},
	Write16:            {0x00: {false, write16Usage()}},
	WriteSame16:        {0x00: {false, writeSame16Usage()}},
	ReadCapacity10:     {0x00: {false, readCapacity10Usage()}},
	ServiceActionIn: {
		ServiceActionReadCapacity16: {true, readCapacity16Usage()},
	},
	OperationCodeMaintenanceIn: {
		ServiceActionReportSupportedOperationCodes: {
			true,
			reportSupportedOperationCodesUsage(),
		},
	},
}

func reportOpcodesAll(command *SCSICommand, returnCommandsTimeoutsDescriptor int) {
	data := make([]byte, 0, 100)
	flags := byte(0x00)
	if returnCommandsTimeoutsDescriptor != 0 {
		flags = byte(0x02) // command timeouts' descriptor present bitmask
	}
	for commandType, commandsByServiceAction := range commandDescriptions {
		for serviceAction, description := range commandsByServiceAction {
			currentFlags := flags
			if description.hasServiceAction {
				// Has service action
				currentFlags |= 0x01
			}
			data = append(
				data,
				byte(commandType),
				// reserved
				0x00,
				// service action
				0x00, serviceAction,
				// reserved
				0x00,
				currentFlags,
				//command length
				0x00, description.length(),
			)
			if returnCommandsTimeoutsDescriptor != 0 {
				data = append(data, timeoutsDescriptor...)
			}
		}
	}
	copy(command.InSDBBuffer.Buffer, MarshalUint32(uint32(len(data))))
	copy(command.InSDBBuffer.Buffer[4:], data)
}

func formatUnitUsage() []byte {
	formatProtectionInformationBitmask := byte(0x80)
	formatDataBitMask := byte(0x10)
	defectListBitMask := byte(0x07)
	return []byte{
		byte(FormatUnit),
		formatProtectionInformationBitmask |
			formatDataBitMask | defectListBitMask,
		// other fields not used
		0x00, 0x00, 0x00, 0x00,
	}
}

func inquiryUsage() []byte {
	enableVitalProductDataBitmask := byte(0x01)
	return []byte{
		byte(Inquiry),
		enableVitalProductDataBitmask,
		// page code
		0xff,
		// allocation length
		0xff, 0xff,
		// control not used
		0x00,
	}
}

func modeSelect10Usage() []byte {
	return []byte{
		byte(ModeSelect10),
		0x00, 0x00,
		0x00, 0x00,
		0x00, 0x00,
		0x00, 0x00,
		0x00, 0x00,
	}
}

func modeSense6Usage() []byte {
	disableBlockDescriptorsBitMask := byte(0x8)
	// first six bit of second request byte
	pageCodeBitMask := byte(0x3f)
	// last two bits of second request byte
	pageControlBitMask := byte(0xc0)
	return []byte{
		byte(ModeSense6),
		disableBlockDescriptorsBitMask,
		pageControlBitMask | pageCodeBitMask,
		// subpage code
		0xff,
		// allocation length
		0xff,
		0x00,
	}
}

func modeSense10Usage() []byte {
	disableBlockDescriptorsBitMask := byte(0x8)
	// first six bit of second request byte
	pageCodeBitMask := byte(0x3f)
	// last two bits of second request byte
	pageControlBitMask := byte(0xc0)
	return []byte{
		byte(ModeSense6),
		disableBlockDescriptorsBitMask,
		pageControlBitMask | pageCodeBitMask,
		// subpage code
		0xff,
		// reserved
		0x00, 0x00, 0x00,
		// allocation length
		0xff, 0xff,
		// control
		0x00,
	}
}

func read10Usage() []byte {
	const readProtectBitMask = byte(0xe0)
	// despite not using DPO and FUA
	// (We do not perform any actions),
	// we allow these fields to be set
	const dpoFuaBitmask = byte(0x18)
	return []byte{
		byte(Read10),
		readProtectBitMask | dpoFuaBitmask,
		// Logical block address
		0xff, 0xff, 0xff, 0xff,
		// Reserved
		0x00,
		// Transfer length
		0xff, 0xff,
		// control
		0x00,
	}
}

func read16Usage() []byte {
	const readProtectBitMask = byte(0xe0)
	// despite not using DPO and FUA
	// (We do not perform any actions),
	// we allow these fields to be set
	const dpoFuaBitmask = byte(0x18)
	return []byte{
		byte(Read16),
		readProtectBitMask | dpoFuaBitmask,
		//Logical block address
		0xff, 0xff, 0xff, 0xff,
		0xff, 0xff, 0xff, 0xff,
		// Transfer length
		0xff, 0xff, 0xff, 0xff,
		// Reserved
		0x00,
		//Control
		0x00,
	}
}

func reportLunsUsage() []byte {
	return []byte{
		byte(ReportLuns),
		// Reserved
		0x00,
		// Select report
		0x00,
		// Reserved
		0x00, 0x00, 0x00,
		// Allocation length
		0xff, 0xff, 0xff, 0xff,
		// Reserved
		0x00,
		// Control
		0x00,
	}
}

func requestSenseUsage() []byte {
	return []byte{
		byte(RequestSense),
		0x00, 0x00, 0xff, 0x00, 0x00,
	}
}

func startStopUsage() []byte {
	return []byte{
		byte(StartStop),
		0x00, 0x00, 0x00, 0x00, 0x00,
	}
}

func synchronizeCache10Usage() []byte {
	return []byte{
		byte(SynchronizeCache10),
		// Reserved
		0x00,
		// Logical block address
		0xff, 0xff, 0xff, 0xff,
		// Reserved
		0x00,
		// Number of logical blocks
		0xff, 0xff,
		// control
		0x00,
	}
}
func synchronizeCache16Usage() []byte {
	return []byte{
		byte(SynchronizeCache16),
		// Reserved
		0x00,
		//Logical block address
		0xff, 0xff, 0xff, 0xff,
		0xff, 0xff, 0xff, 0xff,
		// Number of logical blocks
		0xff, 0xff, 0xff, 0xff,
		// Reserved
		0x00,
		//Control
		0x00,
	}
}

func testUnitReadyUsage() []byte {
	return []byte{
		byte(TestUnitReady),
		// Reserved
		0x00, 0x00, 0x00, 0x00,
		// Control
		0x00,
	}
}

func write10Usage() []byte {
	const (
		writeProtectBitMask = byte(0xe0)
		// despite not using DPO and FUA
		// (We do not perform any actions),
		// we allow these fields to be set
		dpoFuaBitmask = byte(0x18)
	)
	return []byte{
		byte(Write10),
		writeProtectBitMask | dpoFuaBitmask,
		// Logical block address
		0xff, 0xff, 0xff, 0xff,
		// Reserved
		0x00,
		// Transfer length
		0xff, 0xff,
		// control
		0x00,
	}
}

func write16Usage() []byte {
	const (
		writeProtectBitMask = byte(0xe0)
		// despite not using DPO and FUA
		// (We do not perform any actions),
		// we allow these fields to be set
		dpoFuaBitmask = byte(0x18)
	)

	return []byte{
		byte(Write16),
		writeProtectBitMask | dpoFuaBitmask,
		//Logical block address
		0xff, 0xff, 0xff, 0xff,
		0xff, 0xff, 0xff, 0xff,
		// Transfer length
		0xff, 0xff, 0xff, 0xff,
		// Reserved
		0x00,
		//Control
		0x00,
	}
}

func writeSame16Usage() []byte {
	const (
		anchorBitMask       = byte(0x10)
		unmapBitMask        = byte(0x08)
		writeProtectBitMask = byte(0xe0)
		obsoleteBitMask     = byte(0x06)
	)
	firstBitMask := anchorBitMask | unmapBitMask | writeProtectBitMask | obsoleteBitMask
	return []byte{
		byte(WriteSame16),
		firstBitMask,
		//Logical block address
		0xff, 0xff, 0xff, 0xff,
		0xff, 0xff, 0xff, 0xff,
		// Transfer length
		0xff, 0xff, 0xff, 0xff,
		// Reserved
		0x00,
		//Control
		0x00,
	}
}
func readCapacity10Usage() []byte {
	return []byte{
		byte(ReadCapacity10),
		0x00,
		// we check obsolete bytes for zeroes
		0xff, 0xff, 0xff, 0xff,
		0x00,
		0x00,
		// obsolete byte
		0x01,
		// control
		0x00,
	}
}

func readCapacity16Usage() []byte {
	return []byte{
		byte(ServiceActionIn),
		// service action
		0x1f,
		// obsolete
		0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
		0xff, 0xff, 0xff, 0xff,
		0x00,
		0x00,
	}
}

func reportSupportedOperationCodesUsage() []byte {
	const reportingOptionsBitmask = byte(0x07)
	const returnCommandTimeoutDescriptor = byte(0x80)
	return []byte{
		byte(OperationCodeMaintenanceIn),
		// service action bitmask
		0x1f,
		reportingOptionsBitmask | returnCommandTimeoutDescriptor,
		// requested operation code
		0xff,
		// requested service action
		0xff, 0xff,
		// allocation length
		0xff, 0xff, 0xff, 0xff,
		// Reserved
		0x00,
		// control
		0x00,
	}
}

func reportSingleOpCode(
	command *SCSICommand,
	reportingOptions byte,
	returnCommandsTimeoutsDescriptor int,
) SAMStat {
	operationCode := CommandType(command.SCB[3])
	data := make([]byte, 0, 16)
	serviceAction := byte(0x00)
	switch reportingOptions {
	case reportSingleServiceActionReportingOption,
		reportSingleReporingOptionAllowBoth:
		// service action is actually bytes 4 and 5,
		// but since all service actions
		// are explicitly single byte,
		// we can just parse the last field,
		// since the value is encoded in big endian
		serviceAction = command.SCB[5]
	}
	commandDescriptionsByServiceAction, ok := commandDescriptions[operationCode]
	if !ok {
		BuildSenseData(command, IllegalRequest, AscInvalidFieldInCdb)
		return SAMStatCheckCondition
	}
	commandDescription, ok := commandDescriptionsByServiceAction[serviceAction]
	if !ok {
		BuildSenseData(command, IllegalRequest, AscInvalidFieldInCdb)
		return SAMStatCheckCondition
	}
	switch reportingOptions {
	case reportSingleReportingOption:
		if commandDescription.hasServiceAction {
			BuildSenseData(command, IllegalRequest, AscInvalidFieldInCdb)
			return SAMStatCheckCondition
		}
	case reportSingleServiceActionReportingOption:
		if !commandDescription.hasServiceAction {
			BuildSenseData(command, IllegalRequest, AscInvalidFieldInCdb)
			return SAMStatCheckCondition
		}
	case reportSingleReporingOptionAllowBoth:
		break
	default:
		BuildSenseData(command, IllegalRequest, AscInvalidFieldInCdb)
		return SAMStatCheckCondition
	}
	data = commandDescription.content
	secondByte := byte(0x00)
	if returnCommandsTimeoutsDescriptor != 0 {
		secondByte = byte(0x80)
	}
	response := []byte{
		// Reserved
		0x00,
		// CTDP, Reserved,CDLP,SUPPORT
		// CTDP - command timeouts descriptor present
		// CDLP - command duration limit page
		// the bit is set to 0, since we
		// do not have Command Duration Limit MODE PAGE
		// (neither A nor B)
		secondByte,
		// CDB Size
		// Data does not exceed 255 bits
		0x00, byte(len(data)),
	}
	response = append(response, data...)
	if returnCommandsTimeoutsDescriptor != 0 {
		response = append(response, timeoutsDescriptor...)
	}
	copy(command.InSDBBuffer.Buffer, response)
	return SAMStatGood
}

func SPCReportSupportedOperationCodes(command *SCSICommand) SAMStat {
	log := logger.GetLogger()
	const reportingOptionsBitmask = byte(0x07)
	const returnCommandTimeoutDescriptorBitMask = byte(0x80)
	reportingOptions := command.SCB[2] & reportingOptionsBitmask
	returnCommandsTimeoutsDescriptor := int(command.SCB[2] & returnCommandTimeoutDescriptorBitMask)
	switch reportingOptions {
	case reportAllReportingOption: /* report all */
		log.Debugf("Service Action: report all")
		reportOpcodesAll(command, returnCommandsTimeoutsDescriptor)
		return SAMStatGood
	case reportSingleReportingOption,
		reportSingleServiceActionReportingOption,
		reportSingleReporingOptionAllowBoth:
		return reportSingleOpCode(
			command,
			reportingOptions,
			returnCommandsTimeoutsDescriptor,
		)
	default:
		log.Errorf("Unsupported reporting options %d", reportingOptions)
		if command.InSDBBuffer != nil {
			command.InSDBBuffer.Residual = 0
		}
		BuildSenseData(command, IllegalRequest, AscInvalidFieldInCdb)
		return SAMStatCheckCondition
	}
}
