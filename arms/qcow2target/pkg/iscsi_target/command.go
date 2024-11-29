// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package iscsi_target

import (
	"bytes"
	"fmt"
	"qcow2target/pkg/logger"
	"qcow2target/pkg/scsi"
	"strings"
	"time"
)

type OpCode int

const (
	// Defined on the initiator.
	OpNoopOut     OpCode = 0x00
	OpSCSICmd            = 0x01
	OpSCSITaskReq        = 0x02
	OpLoginReq           = 0x03
	OpTextReq            = 0x04
	OpSCSIOut            = 0x05
	OpLogoutReq          = 0x06
	OpSNACKReq           = 0x10
	// Defined on the target.
	OpNoopIn       OpCode = 0x20
	OpSCSIResp            = 0x21
	OpSCSITaskResp        = 0x22
	OpLoginResp           = 0x23
	OpTextResp            = 0x24
	OpSCSIIn              = 0x25
	OpLogoutResp          = 0x26
	OpReady               = 0x31
	OpAsync               = 0x32
	OpReject              = 0x3f
)

const (
	MaxBurstLength           uint32 = 262144
	MaxRecvDataSegmentLength uint32 = 65536
)

var opCodeMap = map[OpCode]string{
	OpNoopOut:      "NOP-Out",
	OpSCSICmd:      "SCSI Command",
	OpSCSITaskReq:  "SCSI Task Management FunctionRequest",
	OpLoginReq:     "Login Request",
	OpTextReq:      "Text Request",
	OpSCSIOut:      "SCSI Data-Out (write)",
	OpLogoutReq:    "Logout Request",
	OpSNACKReq:     "SNACK Request",
	OpNoopIn:       "NOP-In",
	OpSCSIResp:     "SCSI Response",
	OpSCSITaskResp: "SCSI Task Management Function Response",
	OpLoginResp:    "Login Response",
	OpTextResp:     "Text Response",
	OpSCSIIn:       "SCSI Data-In (read)",
	OpLogoutResp:   "Logout Response",
	OpReady:        "Ready To Transfer (R2T)",
	OpAsync:        "Asynchronous Message",
	OpReject:       "Reject",
}

const DataPadding = 4

type ISCSITaskManagementFunc struct {
	Result            byte
	TaskFunc          uint32
	ReferencedTaskTag uint32
}

type ISCSICommand struct {
	OperationCode OpCode
	RawHeader     []byte
	DataLen       int
	RawData       []byte
	Final         bool
	FinalInSeq    bool
	Immediate     bool
	TaskTag       uint32
	StartTime     time.Time
	ExpCmdSN      uint32
	MaxCmdSN      uint32
	AHSLen        int
	Resid         uint32

	// Connection ID.
	ConnID uint16
	// CmdSN - Command sequence number.
	// the current command Sequence Number, advanced by 1 on
	// each command shipped except for commands marked for immediate
	// delivery. Command sequence number always contains the number to be assigned to
	// the next Command PDU.
	CmdSN uint32
	// Expected status serial.
	ExpStatSN uint32

	Read, Write bool
	LUN         byte
	// Transit bit.
	Transit bool
	// Continue bit.
	Continue bool
	// Current Stage, Next Stage.
	CurrentStage, NextStage iSCSILoginStage
	// Initiator part of the SSID.
	ISID uint64
	// Target-assigned Session Identifying Handle.
	TSIH uint16
	// Status serial number.
	StatSN uint32

	// For login response.
	StatusClass  uint8
	StatusDetail uint8

	// SCSI commands
	SCSIOpCode      byte
	ExpectedDataLen uint32
	CDB             []byte
	Status          byte
	SCSIResponse    byte

	// Task request
	ISCSITaskManagementFunc

	// R2T
	R2TSN         uint32
	DesiredLength uint32

	// Data-In/Out
	HasStatus bool
	// DataSequenceNumber DataSN field in iSCSI
	// For input (read) or bidirectional Data-In PDUs, the DataSN is the
	// input PDU number within the data transfer for the command identified
	// by the Initiator Task Tag.
	// For output (write) data PDUs, the DataSN is the Data-Out PDU number
	// within the current output sequence.  The current output sequence is
	// either identified by the Initiator Task Tag (for unsolicited data) or
	// is a data sequence generated for one R2T (for data solicited through
	// R2T).
	DataSequenceNumber uint32
	BufferOffset       uint32
}

func (iscsiCommand *ISCSICommand) Bytes() []byte {
	switch iscsiCommand.OperationCode {
	case OpLoginResp:
		return iscsiCommand.loginResponseBytes()
	case OpLogoutResp:
		return iscsiCommand.logoutResponseBytes()
	case OpSCSIResp:
		return iscsiCommand.scsiCmdRespBytes()
	case OpSCSIIn:
		return iscsiCommand.dataInBytes()
	case OpTextResp:
		return iscsiCommand.textRespBytes()
	case OpNoopIn:
		return iscsiCommand.noopInBytes()
	case OpSCSITaskResp:
		return iscsiCommand.scsiTMFRespBytes()
	case OpReady:
		return iscsiCommand.r2tRespBytes()
	}
	return nil
}

func (iscsiCommand *ISCSICommand) String() string {
	var s []string
	s = append(s, fmt.Sprintf("Op: %v", opCodeMap[iscsiCommand.OperationCode]))
	s = append(s, fmt.Sprintf("Final = %v", iscsiCommand.Final))
	s = append(s, fmt.Sprintf("Immediate = %v", iscsiCommand.Immediate))
	s = append(s, fmt.Sprintf("Data Segment Length = %d", iscsiCommand.DataLen))
	s = append(s, fmt.Sprintf("Task Tag = %x", iscsiCommand.TaskTag))
	s = append(s, fmt.Sprintf("AHS Length = %d", iscsiCommand.AHSLen))
	switch iscsiCommand.OperationCode {
	case OpLoginReq:
		s = append(s, fmt.Sprintf("ISID = %x", iscsiCommand.ISID))
		s = append(s, fmt.Sprintf("Transit = %v", iscsiCommand.Transit))
		s = append(s, fmt.Sprintf("Continue = %v", iscsiCommand.Continue))
		s = append(s, fmt.Sprintf("Current Stage = %v", iscsiCommand.CurrentStage))
		s = append(s, fmt.Sprintf("Next Stage = %v", iscsiCommand.NextStage))
	case OpLoginResp:
		s = append(s, fmt.Sprintf("ISID = %x", iscsiCommand.ISID))
		s = append(s, fmt.Sprintf("Transit = %v", iscsiCommand.Transit))
		s = append(s, fmt.Sprintf("Continue = %v", iscsiCommand.Continue))
		s = append(s, fmt.Sprintf("Current Stage = %v", iscsiCommand.CurrentStage))
		s = append(s, fmt.Sprintf("Next Stage = %v", iscsiCommand.NextStage))
		s = append(s, fmt.Sprintf("Status Class = %d", iscsiCommand.StatusClass))
		s = append(s, fmt.Sprintf("Status Detail = %d", iscsiCommand.StatusDetail))
	case OpSCSICmd, OpSCSIOut, OpSCSIIn:
		s = append(s, fmt.Sprintf("LUN = %d", iscsiCommand.LUN))
		s = append(s, fmt.Sprintf("ExpectedDataLen = %d", iscsiCommand.ExpectedDataLen))
		s = append(s, fmt.Sprintf("CmdSN = %d", iscsiCommand.CmdSN))
		s = append(s, fmt.Sprintf("ExpStatSN = %d", iscsiCommand.ExpStatSN))
		s = append(s, fmt.Sprintf("Read = %v", iscsiCommand.Read))
		s = append(s, fmt.Sprintf("Write = %v", iscsiCommand.Write))
		s = append(s, fmt.Sprintf("CDB = %x", iscsiCommand.CDB))
	case OpSCSIResp:
		s = append(s, fmt.Sprintf("StatSN = %d", iscsiCommand.StatSN))
		s = append(s, fmt.Sprintf("ExpCmdSN = %d", iscsiCommand.ExpCmdSN))
		s = append(s, fmt.Sprintf("MaxCmdSN = %d", iscsiCommand.MaxCmdSN))
	}
	return strings.Join(s, "\n")
}

func parseHeader(data []byte) (*ISCSICommand, error) {
	if len(data) != BasicHeaderSegmentSize {
		return nil, fmt.Errorf("garbled header")
	}
	// TODO: sync.Pool
	command := &ISCSICommand{
		Immediate:     0x40&data[0] == 0x40,
		OperationCode: OpCode(data[0] & IscsiOpcodeMask),
		Final:         0x80&data[1] == 0x80,
		AHSLen:        int(data[4]) * 4,
		DataLen:       int(uint64FromByte(data[5:8])),
		TaskTag:       uint32(uint64FromByte(data[16:20])),
		StartTime:     time.Now(),
	}
	switch command.OperationCode {
	case OpSCSICmd:
		// According to RFC3720 10.2.1.7
		// Logical Unit field must be formatted according
		// to SAM2.
		// Since we usually don't have more than 255 logical units,
		// it is safe to say we use single level logical unit number structure,
		// described in SAM2r24 (T10/1157-D revision 24) in section 4.9.3
		// https://www.yumpu.com/en/document/read/31707724/scsi-architecture-model-2pdf
		command.LUN = data[9]
		command.ExpectedDataLen = uint32(uint64FromByte(data[20:24]))
		command.CmdSN = uint32(uint64FromByte(data[24:28]))
		command.Read = data[1]&0x40 == 0x40
		command.Write = data[1]&0x20 == 0x20
		command.CDB = data[32:48]
		command.ExpStatSN = uint32(uint64FromByte(data[28:32]))
		command.SCSIOpCode = command.CDB[0]
		SCSIOpcode := scsi.CommandType(command.SCSIOpCode)
		switch SCSIOpcode {
		case scsi.Read16, scsi.Read10:
			command.Read = true
		case scsi.Write16, scsi.Write10:
			command.Write = true
		}
		fallthrough
	case OpSCSITaskReq:
		command.ReferencedTaskTag = uint32(uint64FromByte(data[20:24]))
		command.TaskFunc = uint32(data[1] & IscsiFlagTmFuncMask)
	case OpSCSIResp:
	case OpSCSIOut:
		// According to RFC3720 10.2.1.7
		// Logical Unit field must be formatted according
		// to SAM2.
		// Since we usually don't have more than 255 logical units,
		// it is safe to say we use single level logical unit number structure,
		// described in SAM2r24 (T10/1157-D revision 24) in section 4.9.3
		// https://www.yumpu.com/en/document/read/31707724/scsi-architecture-model-2pdf
		command.LUN = data[9]
		command.ExpStatSN = uint32(uint64FromByte(data[28:32]))
		command.DataSequenceNumber = uint32(uint64FromByte(data[36:40]))
		command.BufferOffset = uint32(uint64FromByte(data[40:44]))
	case OpNoopOut:
		command.Transit = command.Final
		command.Continue = data[1]&0x40 == 0x40
		if command.Continue && command.Transit {
			// rfc7143 11.12.2
			return nil, fmt.Errorf("transit and continue bits set in same login request")
		}
		command.CurrentStage = iSCSILoginStage(data[1]&0xc) >> 2
		command.NextStage = iSCSILoginStage(data[1] & 0x3)
		command.ISID = uint64FromByte(data[8:14])
		command.TSIH = uint16(uint64FromByte(data[14:16]))
		command.ReferencedTaskTag = uint32(uint64FromByte(data[20:24]))
		command.CmdSN = uint32(uint64FromByte(data[24:28]))
		command.ExpStatSN = uint32(uint64FromByte(data[28:32]))
	case OpLoginReq, OpTextReq, OpLogoutReq:
		command.Transit = command.Final
		command.Continue = data[1]&0x40 == 0x40
		if command.Continue && command.Transit {
			// rfc7143 11.12.2
			return nil, fmt.Errorf("transit and continue bits set in same login request")
		}
		command.CurrentStage = iSCSILoginStage(data[1]&0xc) >> 2
		command.NextStage = iSCSILoginStage(data[1] & 0x3)
		command.ISID = uint64FromByte(data[8:14])
		command.TSIH = uint16(uint64FromByte(data[14:16]))
		command.ConnID = uint16(uint64FromByte(data[20:22]))
		command.CmdSN = uint32(uint64FromByte(data[24:28]))
		command.ExpStatSN = uint32(uint64FromByte(data[28:32]))
	case OpLoginResp:
		command.Transit = command.Final
		command.Continue = data[1]&0x40 == 0x40
		if command.Continue && command.Transit {
			// rfc7143 11.12.2
			return nil, fmt.Errorf("transit and continue bits set in same login request")
		}
		command.CurrentStage = iSCSILoginStage(data[1]&0xc) >> 2
		command.NextStage = iSCSILoginStage(data[1] & 0x3)
		command.StatSN = uint32(uint64FromByte(data[24:28]))
		command.ExpCmdSN = uint32(uint64FromByte(data[28:32]))
		command.MaxCmdSN = uint32(uint64FromByte(data[32:36]))
		command.StatusClass = data[36]
		command.StatusDetail = data[37]
	}
	return command, nil
}

func (iscsiCommand *ISCSICommand) scsiCmdRespBytes() []byte {
	// rfc7143 11.4
	buf := bytes.Buffer{}
	buf.WriteByte(byte(OpSCSIResp))
	var flag byte = 0x80
	if iscsiCommand.Resid > 0 {
		if iscsiCommand.Resid > iscsiCommand.ExpectedDataLen {
			flag |= 0x04
		} else {
			flag |= 0x02
		}
	}
	buf.WriteByte(flag)
	buf.WriteByte(iscsiCommand.SCSIResponse)
	buf.WriteByte(iscsiCommand.Status)

	buf.WriteByte(0x00)
	buf.Write(MarshalUint64(uint64(len(iscsiCommand.RawData)))[5:]) // 5-8
	// Skip through to byte 16
	for i := 0; i < 8; i++ {
		buf.WriteByte(0x00)
	}
	buf.Write(MarshalUint64(uint64(iscsiCommand.TaskTag))[4:])
	for i := 0; i < 4; i++ {
		buf.WriteByte(0x00)
	}
	buf.Write(MarshalUint64(uint64(iscsiCommand.StatSN))[4:])
	buf.Write(MarshalUint64(uint64(iscsiCommand.ExpCmdSN))[4:])
	buf.Write(MarshalUint64(uint64(iscsiCommand.MaxCmdSN))[4:])
	for i := 0; i < 2*4; i++ {
		buf.WriteByte(0x00)
	}
	buf.Write(MarshalUint64(uint64(iscsiCommand.Resid))[4:])
	buf.Write(iscsiCommand.RawData)
	dl := len(iscsiCommand.RawData)
	for dl%4 > 0 {
		dl++
		buf.WriteByte(0x00)
	}

	return buf.Bytes()
}

func (iscsiCommand *ISCSICommand) dataInBytes() []byte {
	log := logger.GetLogger()
	// rfc7143 11.7
	dl := iscsiCommand.DataLen
	for dl%4 > 0 {
		dl++
	}
	var buf = make([]byte, 48+dl)
	buf[0] = byte(OpSCSIIn)
	var flag byte
	if iscsiCommand.FinalInSeq || iscsiCommand.Final == true {
		flag |= 0x80
	}
	if iscsiCommand.HasStatus && iscsiCommand.Final == true {
		flag |= 0x01
	}
	log.Debugf("resid: %v, ExpectedDataLen: %v", iscsiCommand.Resid, iscsiCommand.ExpectedDataLen)
	if iscsiCommand.Resid > 0 {
		if iscsiCommand.Resid > iscsiCommand.ExpectedDataLen {
			flag |= 0x04
		} else if iscsiCommand.Resid < iscsiCommand.ExpectedDataLen {
			flag |= 0x02
		}
	}
	buf[1] = flag
	//buf.WriteByte(0x00)
	if iscsiCommand.HasStatus && iscsiCommand.Final == true {
		flag = iscsiCommand.Status
	}
	//buf.WriteByte(flag)
	buf[3] = flag
	copy(buf[5:], MarshalUint64(uint64(iscsiCommand.DataLen))[5:])
	// Skip through to byte 16 Since A bit is not set 11.7.4
	copy(buf[16:], MarshalUint32(iscsiCommand.TaskTag))
	copy(buf[24:], MarshalUint32(iscsiCommand.StatSN))
	copy(buf[28:], MarshalUint32(iscsiCommand.ExpCmdSN))
	copy(buf[32:], MarshalUint32(iscsiCommand.MaxCmdSN))
	copy(buf[36:], MarshalUint32(iscsiCommand.DataSequenceNumber))
	copy(buf[40:], MarshalUint32(iscsiCommand.BufferOffset))
	copy(buf[44:], MarshalUint32(iscsiCommand.Resid))
	if iscsiCommand.ExpectedDataLen != 0 {
		copy(buf[48:], iscsiCommand.RawData[iscsiCommand.BufferOffset:iscsiCommand.BufferOffset+uint32(iscsiCommand.DataLen)])
	}

	return buf
}

func (iscsiCommand *ISCSICommand) textRespBytes() []byte {
	buf := bytes.Buffer{}
	buf.WriteByte(byte(OpTextResp))
	var b byte
	if iscsiCommand.Final {
		b |= 0x80
	}
	if iscsiCommand.Continue {
		b |= 0x40
	}
	// byte 1
	buf.WriteByte(b)

	b = 0
	buf.WriteByte(b)
	buf.WriteByte(b)
	buf.WriteByte(b)
	buf.Write(MarshalUint64(uint64(len(iscsiCommand.RawData)))[5:]) // 5-8
	// Skip through to byte 12
	for i := 0; i < 2*4; i++ {
		buf.WriteByte(0x00)
	}
	buf.Write(MarshalUint64(uint64(iscsiCommand.TaskTag))[4:])
	for i := 0; i < 4; i++ {
		buf.WriteByte(0xff)
	}
	buf.Write(MarshalUint64(uint64(iscsiCommand.StatSN))[4:])
	buf.Write(MarshalUint64(uint64(iscsiCommand.ExpCmdSN))[4:])
	buf.Write(MarshalUint64(uint64(iscsiCommand.MaxCmdSN))[4:])
	for i := 0; i < 3*4; i++ {
		buf.WriteByte(0x00)
	}
	rd := iscsiCommand.RawData
	for len(rd)%4 != 0 {
		rd = append(rd, 0)
	}
	buf.Write(rd)
	return buf.Bytes()
}

func (iscsiCommand *ISCSICommand) noopInBytes() []byte {
	buf := bytes.Buffer{}
	buf.WriteByte(byte(OpNoopIn))
	var b byte
	b |= 0x80
	// byte 1
	buf.WriteByte(b)

	b = 0
	buf.WriteByte(b)
	buf.WriteByte(b)
	buf.WriteByte(b)
	buf.Write(MarshalUint64(uint64(len(iscsiCommand.RawData)))[5:]) // 5-8
	// Skip through to byte 12
	for i := 0; i < 2*4; i++ {
		buf.WriteByte(0x00)
	}
	buf.Write(MarshalUint64(uint64(iscsiCommand.TaskTag))[4:])
	for i := 0; i < 4; i++ {
		buf.WriteByte(0xff)
	}
	buf.Write(MarshalUint64(uint64(iscsiCommand.StatSN))[4:])
	buf.Write(MarshalUint64(uint64(iscsiCommand.ExpCmdSN))[4:])
	buf.Write(MarshalUint64(uint64(iscsiCommand.MaxCmdSN))[4:])
	for i := 0; i < 3*4; i++ {
		buf.WriteByte(0x00)
	}
	rd := iscsiCommand.RawData
	for len(rd)%4 != 0 {
		rd = append(rd, 0)
	}
	buf.Write(rd)
	return buf.Bytes()
}

func (iscsiCommand *ISCSICommand) scsiTMFRespBytes() []byte {
	// rfc7143 11.6
	buf := bytes.Buffer{}
	buf.WriteByte(byte(OpSCSITaskResp))
	buf.WriteByte(0x80)
	buf.WriteByte(iscsiCommand.Result)
	buf.WriteByte(0x00)

	// Skip through to byte 16
	for i := 0; i < 3*4; i++ {
		buf.WriteByte(0x00)
	}
	buf.Write(MarshalUint64(uint64(iscsiCommand.TaskTag))[4:])
	for i := 0; i < 4; i++ {
		buf.WriteByte(0x00)
	}
	buf.Write(MarshalUint64(uint64(iscsiCommand.StatSN))[4:])
	buf.Write(MarshalUint64(uint64(iscsiCommand.ExpCmdSN))[4:])
	buf.Write(MarshalUint64(uint64(iscsiCommand.MaxCmdSN))[4:])
	for i := 0; i < 3*4; i++ {
		buf.WriteByte(0x00)
	}

	return buf.Bytes()
}

func (iscsiCommand *ISCSICommand) r2tRespBytes() []byte {
	// rfc7143 11.8
	buf := bytes.Buffer{}
	buf.WriteByte(byte(OpReady))
	var b byte
	if iscsiCommand.Final {
		b |= 0x80
	}
	buf.WriteByte(b)
	buf.WriteByte(0x00)
	buf.WriteByte(0x00)

	// Skip through to byte 16
	for i := 0; i < 3*4; i++ {
		buf.WriteByte(0x00)
	}
	buf.Write(MarshalUint64(uint64(iscsiCommand.TaskTag))[4:])
	for i := 0; i < 4; i++ {
		buf.WriteByte(0x00)
	}
	buf.Write(MarshalUint64(uint64(iscsiCommand.StatSN))[4:])
	buf.Write(MarshalUint64(uint64(iscsiCommand.ExpCmdSN))[4:])
	buf.Write(MarshalUint64(uint64(iscsiCommand.MaxCmdSN))[4:])
	buf.Write(MarshalUint64(uint64(iscsiCommand.R2TSN))[4:])
	buf.Write(MarshalUint64(uint64(iscsiCommand.BufferOffset))[4:])
	buf.Write(MarshalUint64(uint64(iscsiCommand.DesiredLength))[4:])

	return buf.Bytes()
}
