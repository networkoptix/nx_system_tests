// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package scsi

import (
	"fmt"
	uuid "github.com/satori/go.uuid"
	"qcow2target/pkg/qcow2"
)

type LogicalUnitFactory struct {
	imageFactory *qcow2.ImageFactory
	iscsiId      uint64
}

func newLogicalUnitFactory(imageFactory *qcow2.ImageFactory) LogicalUnitFactory {
	return LogicalUnitFactory{
		imageFactory: imageFactory,
		iscsiId:      1000,
	}
}

type LogicalUnit struct {
	Address             uint64
	Size                uint64
	UUID                uint64
	Path                string
	BsoFlags            int
	BlockShift          uint
	ReserveID           uuid.UUID
	Attrs               SCSILuPhyAttribute
	ModePages           ModePages
	BackingStorage      BackingStore
	ModeBlockDescriptor []byte
	SCSIVendorID        string
	SCSIProductID       string
	SCSIID              string

	TargetLunId byte
}

type LunRepresentation struct {
	LogicalUnitId byte
	FilePath      string
}

func (logicalUnit *LogicalUnit) Init(deviceType SCSIDeviceType) {
	// init LU's phy attribute
	logicalUnit.Attrs.DeviceType = deviceType
	logicalUnit.Attrs.Qualifier = false
	logicalUnit.Attrs.VendorID = "NX"
	logicalUnit.Attrs.ProductID = "QCOWTARGET"
	logicalUnit.Attrs.ProductRev = "0.1"
	/*
	   The PRODUCT SERIAL NUMBER field contains
	   right-aligned ASCII data (see 4.3.1)
	   that is a vendor specific serial number.
	   If the product serial number is not available,
	   the device server shall return ASCII spaces (20h) in this field.
	   leave it with 4 spaces (20h)
	*/
	logicalUnit.Attrs.SCSISN = fmt.Sprintf("qcow2target-beaf-%d%d", 0, logicalUnit.UUID)

	/*
		SCSIID for PAGE83 T10 VENDOR IDENTIFICATION field
		It is going to be the iSCSI target iqn name
		leave it with a default target name
	*/

	logicalUnit.Attrs.SCSIID = "iqn.2008-05.com.networkoptix.ft.arms:iscsi-tgt"

	logicalUnit.Attrs.VersionDescription = [16]byte{
		0x03, 0x20, // SBC-2 no version claimed
		0x09, 0x60, // iSCSI no version claimed
		0x03, 0x00, // SPC-3 no version claimed
		0x00, 0x60, // SAM-3 no version claimed
	}
	if logicalUnit.BlockShift == 0 {
		logicalUnit.BlockShift = DefaultBlockShift
	}
	disconnectReconnectModePageCode := byte(0x02)
	pages := []ModePage{
		// Vendor uniq - However most apps seem to call for mode page 0
		//pages = append(pages, ModePage{0, 0, []byte{}})
		// Disconnect page
		{disconnectReconnectModePageCode, 0, []byte{
			// An interconnect tenancy is a period of time during which
			// a given pair of SCSI ports (i.e., an initiator port and a
			// target port) are accessing the interconnect layer to
			// communicate with each other
			// (e.g., on arbitrated interconnects,
			// a tenancy typically begins when a SCSI port successfully
			// arbitrates for the interconnect and ends when
			// the SCSI port releases the interconnect for use by ot her devices).
			// Data and other information transfers take
			// place during interconnect tenancies
			//
			// BUFFER FULL RATIO field specifies to the target port how full
			// the buffer should be during read operations
			// prior to requesting an interconnect tenancy. Target ports that do not implement
			// the requested ratio should round down to the nearest implemented ratio.
			// The buffer full and buffer empty ratios are numerators of
			// a fractional multiplier that has 256 as its denominator.
			0x80,
			// BUFFER EMPTY RATIO field specifies to the target port how empty the buffer should be during write
			// operations prior to requesting an interconnect tenancy.
			0x80,
			// BUS INACTIVITY LIMIT field specifies the maximum time that the target port is permitted to maintain an
			// interconnect tenancy without data or information transfer.
			// If the bus inactivity limit is exceeded, then the target
			// port shall conclude the interconnect tenancy,
			// within the restrictions placed on it by the applicable SCSI
			// transport protocol.
			// Different SCSI transport protocols define different units of measure for the bus inactivity
			// limit.
			0x00, 0xa,
			// DISCONNECT TIME LIMIT
			0x00, 0x00,
			// CONNECT TIME LIMIT
			0x00, 0x00,
			// MAXIMUM BURST SIZE
			0x00, 0x00,
			0x00,
			// Reserved
			0x00, 0x00,
			// FIRST BURST SIZE
			0x00,
		},
		},
		// Caching Page
		{0x08, 0, []byte{0x14, 0, 0xff, 0xff, 0, 0, 0xff, 0xff, 0xff, 0xff, 0x80, 0x14, 0, 0, 0, 0, 0, 0}},
		// Control page (todo check difference between changeable field and default)
		{0x0a, 0, []byte{2, 0x10, 0, 0, 0, 0, 0, 0, 2, 0}},

		// Control Extensions mode page:  TCMOS:1
		{0x0a, 0x01, []byte{0x04, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0}},
		// Informational Exceptions Control page
		{0x1c, 0, []byte{8, 0, 0, 0, 0, 0, 0, 0, 0, 0}},
	}
	logicalUnit.ModePages = pages
	mbd := MarshalUint32(uint32(0xffffffff))
	if size := logicalUnit.Size >> logicalUnit.BlockShift; size>>32 == 0 {
		mbd = MarshalUint32(uint32(size))
	}
	logicalUnit.ModeBlockDescriptor = append(mbd, MarshalUint32(uint32(1<<logicalUnit.BlockShift))...)
}

func (factory LogicalUnitFactory) NewSCSILu(diskPath string) (*LogicalUnit, error) {
	backing, err := NewQcow2BackingStore(factory.imageFactory)
	if err != nil {
		return nil, err
	}

	var lu = &LogicalUnit{
		BackingStorage: backing,
		BlockShift:     DefaultBlockShift,
		UUID:           factory.iscsiId,
	}

	err = backing.Open(diskPath)
	if err != nil {
		return nil, err
	}
	lu.Size = backing.Size()
	lu.Init(TypeDisk)
	lu.Attrs.Online = true
	lu.Attrs.LogicalBlocksPerPhysicalBlockExponent = 3
	factory.iscsiId += 1
	return lu, nil
}

func NewLUN0() *LogicalUnit {
	backing, _ := NewNull()
	var lu = &LogicalUnit{
		BackingStorage: backing,
		BlockShift:     DefaultBlockShift,
		UUID:           0,
	}

	lu.Size = backing.Size()
	lu.Init(TypeUnknown)
	lu.Attrs.Online = false
	lu.Attrs.LogicalBlocksPerPhysicalBlockExponent = 3
	return lu
}

func (logicalUnit LogicalUnit) Representation() LunRepresentation {
	return LunRepresentation{
		LogicalUnitId: logicalUnit.TargetLunId,
		FilePath:      logicalUnit.BackingStorage.GetPath(),
	}
}

func (logicalUnit *LogicalUnit) PerformCommand(command *SCSICommand) SAMStat {
	switch CommandType(command.OperationCode) {
	case TestUnitReady:
		return SPCTestUnit(logicalUnit, command)
	case RequestSense:
		return SPCRequestSense(command)
	case FormatUnit:
		return SBCFormatUnit(logicalUnit, command)
	case Inquiry:
		return SPCInquiry(logicalUnit, command)
	case StartStop:
		return SBCStartStop(logicalUnit, command)
	case ReadCapacity10:
		return SBCReadCapacity(logicalUnit, command)
	case ModeSelect10:
		return SBCModeSelect()
	case ModeSense10:
		return SPCModeSense10(logicalUnit, command)
	case ModeSense6:
		return SPCModeSense6(logicalUnit, command)
	case Read10:
		return SBCRead(logicalUnit, command)
	case Read16:
		return SBCRead(logicalUnit, command)
	case Write10:
		return SbcWrite(logicalUnit, command)
	case Write16:
		return SbcWrite(logicalUnit, command)
	case SynchronizeCache10:
		return SbcSyncCache(logicalUnit, command)
	case SynchronizeCache16:
		return SbcSyncCache(logicalUnit, command)
	case WriteSame16:
		return SbcWriteSame16(logicalUnit, command)
	case ReportLuns:
		return SPCReportLuns(command)
	case OperationCodeMaintenanceIn:
		if command.SCB[1]&0x1f == ServiceActionReportSupportedOperationCodes {
			return SPCReportSupportedOperationCodes(command)
		} else {
			if command.InSDBBuffer != nil {
				command.InSDBBuffer.Residual = 0
			}
			BuildSenseData(command, IllegalRequest, AscInvalidFieldInCdb)
			return SAMStatCheckCondition
		}
	case ServiceActionIn:
		if command.SCB[1]&0x1f == ServiceActionReadCapacity16 {
			return SBCReadCapacity16(logicalUnit, command)
		} else {
			if command.InSDBBuffer != nil {
				command.InSDBBuffer.Residual = 0
			}
			BuildSenseData(command, IllegalRequest, AscInvalidFieldInCdb)
			return SAMStatCheckCondition
		}
	default:
		BuildSenseData(command, IllegalRequest, AscInvalidOpCode)
		return SAMStatCheckCondition
	}
}
