// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package scsi

type CommandError struct {
	senseCode           byte
	additionalSenseCode AdditionalSenseCode
}

const (
	NoSense        byte = 0x00
	NotReady       byte = 0x02
	MediumError    byte = 0x03
	IllegalRequest byte = 0x05
)

type AdditionalSenseCode uint16

var (
	// Key 0: No Sense Errors
	NoAdditionalSense AdditionalSenseCode = 0x0000

	// Key 1: Recovered Errors
	AscWriteError AdditionalSenseCode = 0x0c00
	AscReadError  AdditionalSenseCode = 0x1100

	// Key 2: Not ready
	AscBecomingReady    AdditionalSenseCode = 0x0401
	AscMediumNotPresent AdditionalSenseCode = 0x3a00

	// Key 5: Illegal Request
	AscInvalidOpCode     AdditionalSenseCode = 0x2000
	AscLbaOutOfRange     AdditionalSenseCode = 0x2100
	AscInvalidFieldInCdb AdditionalSenseCode = 0x2400
	AscSavingParmsUnsup  AdditionalSenseCode = 0x3900
)
