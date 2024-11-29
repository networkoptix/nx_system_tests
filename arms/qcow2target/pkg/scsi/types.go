// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package scsi

import (
	"errors"
	"fmt"
	uuid "github.com/satori/go.uuid"
)

type CommandType byte

const (
	FormatUnit      CommandType = 0x04
	Inquiry         CommandType = 0x12
	ModeSelect10    CommandType = 0x55
	ModeSense6      CommandType = 0x1a
	ModeSense10     CommandType = 0x5
	Read10          CommandType = 0x28
	Read16          CommandType = 0x88
	ServiceActionIn CommandType = 0x9e
	ReportLuns      CommandType = 0xa0

	ReadCapacity10             CommandType = 0x25
	OperationCodeMaintenanceIn CommandType = 0xa3
	// ReportSupportedTaskManagementFunctions with the same opcode
	RequestSense       CommandType = 0x03
	StartStop          CommandType = 0x1b
	SynchronizeCache10 CommandType = 0x35
	SynchronizeCache16 CommandType = 0x91
	TestUnitReady      CommandType = 0x00
	Write10            CommandType = 0x2a
	Write16            CommandType = 0x8a
	WriteSame16        CommandType = 0x93
)

const (
	ServiceActionReportSupportedOperationCodes byte = 0x0c
	ServiceActionReadCapacity16                byte = 0x10
)

type TargetState int
type DataDirection int

const (
	DataWrite = 1 + iota
	DataRead
	DataBidirection
)

type SenseBuffer struct {
	Buffer []byte
	Length uint32
}

type SCSIDataBuffer struct {
	Buffer         []byte
	Length         uint32
	TransferLength uint32
	Residual       uint32
}

type SCSICommand struct {
	OperationCode     byte
	Target            *SCSITarget
	Direction         DataDirection
	InSDBBuffer       *SCSIDataBuffer
	OutSDBBuffer      *SCSIDataBuffer
	RelTargetPortID   uint16
	TargetPortGroupId uint16
	TargetPortName    string
	// Command ITN ID
	ITNexusID      uuid.UUID
	Offset         uint64
	TransferLength uint32
	SCB            []byte
	SCBLength      int
	LogicalUnit    byte
	Attribute      int
	Tag            uint64
	Result         byte
	SenseBuffer    *SenseBuffer
	ITNexus        *ITNexus
	ITNexusLuInfo  *ITNexusLuInfo
}

type ITNexus struct {
	// UUID v1
	ID uuid.UUID
	// For protocol spec identifer
	Tag string
}

type ITNexusLuInfo struct {
	Lu      *LogicalUnit
	ID      uint64
	Prevent int
}

type SCSILuPhyAttribute struct {
	SCSIID             string
	SCSISN             string
	NumID              uint64
	VendorID           string
	ProductID          string
	ProductRev         string
	VersionDescription [16]byte
	// Peripheral device type
	DeviceType SCSIDeviceType
	// Peripheral Qualifier
	Qualifier bool
	// Logical Unit online
	Online                                bool
	LogicalBlocksPerPhysicalBlockExponent int // LBPPBE
	// Lowest aligned LBA
	LowestAlignedLBA int
}

const (
	DefaultBlockShift uint = 9
)

const (
	SamStatGood                byte = 0x00
	SamStatCheckCondition      byte = 0x02
	SamStatBusy                byte = 0x08
	SamStatReservationConflict byte = 0x18
	SamStatTaskAborted         byte = 0x40
)

type SAMStat struct {
	Stat byte
	Err  error
}

var (
	SAMStatGood           = SAMStat{SamStatGood, nil}
	SAMStatCheckCondition = SAMStat{SamStatCheckCondition, errors.New("check condition")}
	SAMStatBusy           = SAMStat{SamStatBusy, errors.New("busy")}

	SAMStatReservationConflict = SAMStat{SamStatReservationConflict, errors.New("reservation conflict")}
)

type SCSIDeviceType byte

const (
	TypeDisk    SCSIDeviceType = 0x00
	TypeUnknown SCSIDeviceType = 0x1f
)

func OperationCodeToString(commandType CommandType) string {
	types := map[CommandType]string{
		FormatUnit:                 "FormatUnit",
		Inquiry:                    "Inquiry",
		ModeSelect10:               "ModeSelect10",
		ModeSense6:                 "ModeSense6",
		ModeSense10:                "ModeSense10",
		Read10:                     "Read10",
		Read16:                     "Read16",
		ServiceActionIn:            "ServiceActionIn",
		ReportLuns:                 "ReportLuns",
		OperationCodeMaintenanceIn: "OperationCodeMaintenanceIn",
		RequestSense:               "RequestSense",
		StartStop:                  "StartStop",
		SynchronizeCache10:         "SynchronizeCache10",
		SynchronizeCache16:         "SynchronizeCache16",
		TestUnitReady:              "TestUnitReady",
		Write10:                    "Write10",
		Write16:                    "Write16",
		WriteSame16:                "WriteSame16",
	}
	result, ok := types[commandType]
	if !ok {
		return fmt.Sprintf("0x%x", int(commandType))
	}
	return result
}
