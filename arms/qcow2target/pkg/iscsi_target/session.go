// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package iscsi_target

import (
	"fmt"
	uuid "github.com/satori/go.uuid"
	"qcow2target/pkg/logger"
	"qcow2target/pkg/scsi"
	"strconv"
	"strings"
	"sync"
)

var (
	SessionNormal    = 0
	SessionDiscovery = 1
)

var DigestCrc32c uint = 1 << 1
var DigestNone uint = 1 << 0
var DigestAll = DigestNone | DigestCrc32c

const BasicHeaderSegmentSize = 48

const (
	MaxQueueCmdMin = 1
	MaxQueueCmdDef = 128
	MaxQueueCmdMax = 512
)

const (
	IscsiParamMaxRecvDlength = iota
	IscsiParamHdrdgstEn
	IscsiParamDatadgstEn
	IscsiParamInitialR2tEn
	IscsiParamMaxR2t
	IscsiParamImmDataEn
	IscsiParamFirstBurst
	IscsiParamMaxBurst
	IscsiParamPduInorderEn
	IscsiParamDataseqInorderEn
	IscsiParamErl
	IscsiParamIfmarkerEn
	IscsiParamOfmarkerEn
	IscsiParamDefaulttime2wait
	IscsiParamDefaulttime2retain
	IscsiParamOfmarkint
	IscsiParamIfmarkint
	IscsiParamMaxconnections
	IscsiParamRdmaExtensions // iSCSI Extensions for RDMA (RFC5046)
	IscsiParamTargetRdsl
	IscsiParamInitiatorRdsl
	IscsiParamMaxOutstPdu

	IscsiParamFirstLocal     // "local" params, never sent to the initiator
	IscsiParamMaxXmitDlength = IscsiParamFirstLocal
	IscsiParamMaxQueueCmd
)

type ISCSISessionParam struct {
	idx   uint
	State int
	Value uint
}
type ISCSISessionParamList []ISCSISessionParam

func (list ISCSISessionParamList) Len() int {
	return len(list)
}

func (list ISCSISessionParamList) Less(i, j int) bool {
	if list[i].idx <= list[j].idx {
		return true
	} else {
		return false
	}
}

func (list ISCSISessionParamList) Swap(i, j int) {
	list[i], list[j] = list[j], list[i]
}

// The defaults here are according to the spec and must not be changed,
// otherwise the initiator may make the wrong assumption.  If you want
// to change a value, edit the value in iscsi_target_create.
//
// The param MaxXmitDataSegmentLength doesn't really exist.  It's a way
// to remember the RDSL of the initiator, which defaults to 8k if he has
// not told us otherwise.

type KeyConvFunc func(value string) (uint, bool)
type KeyInConvFunc func(value uint) string

type iscsiSessionKeys struct {
	idx        uint
	constValue bool
	def        uint
	min        uint
	max        uint
	conv       KeyConvFunc
	inConv     KeyInConvFunc
}

func digestKeyConv(value string) (uint, bool) {
	var crc uint
	valueArray := strings.Split(value, ",")
	if len(valueArray) == 0 {
		return crc, false
	}
	for _, tmpV := range valueArray {
		if strings.EqualFold(tmpV, "crc32c") {
			crc |= DigestCrc32c
		} else if strings.EqualFold(tmpV, "none") {
			crc |= DigestNone
		} else {
			return crc, false
		}
	}

	return crc, true
}

func digestKeyInConv(value uint) string {
	str := ""
	switch value {
	case DigestNone:
		str = "None"
	case DigestCrc32c:
		str = "CRC32C"
	case DigestAll:
		str = "None,CRC32C"
	}
	return str
}

func numberKeyConv(value string) (uint, bool) {
	v, err := strconv.Atoi(value)
	if err == nil {
		return uint(v), true
	}
	return uint(0), false
}

func numberKeyInConv(value uint) string {
	return strconv.Itoa(int(value))
}

func boolKeyConv(value string) (uint, bool) {
	if strings.EqualFold(value, "yes") {
		return 1, true
	} else if strings.EqualFold(value, "no") {
		return 0, true
	}
	return 0, false
}

func boolKeyInConv(value uint) string {
	if value == 0 {
		return "No"
	}
	return "Yes"
}

var sessionKeys = map[string]*iscsiSessionKeys{
	// ISCSI_PARAM_MAX_RECV_DLENGTH
	"MaxRecvDataSegmentLength": {IscsiParamMaxRecvDlength, true, 65536, 512, 16777215, numberKeyConv, numberKeyInConv},
	// ISCSI_PARAM_HDRDGST_EN
	"HeaderDigest": {IscsiParamHdrdgstEn, false, DigestNone, DigestNone, DigestAll, digestKeyConv, digestKeyInConv},
	// ISCSI_PARAM_DATADGST_EN
	"DataDigest": {IscsiParamDatadgstEn, false, DigestNone, DigestNone, DigestAll, digestKeyConv, digestKeyInConv},
	// ISCSI_PARAM_INITIAL_R2T_EN
	"InitialR2T": {IscsiParamInitialR2tEn, true, 1, 0, 1, boolKeyConv, boolKeyInConv},
	// ISCSI_PARAM_MAX_R2T
	"MaxOutstandingR2T": {IscsiParamMaxR2t, true, 1, 1, 65535, numberKeyConv, numberKeyInConv},
	// ISCSI_PARAM_IMM_DATA_EN
	"ImmediateData": {IscsiParamImmDataEn, true, 1, 0, 1, boolKeyConv, boolKeyInConv},
	// ISCSI_PARAM_FIRST_BURST
	"FirstBurstLength": {IscsiParamFirstBurst, true, 65536, 512, 16777215, numberKeyConv, numberKeyInConv},
	// ISCSI_PARAM_MAX_BURST
	"MaxBurstLength": {IscsiParamMaxBurst, true, 262144, 512, 16777215, numberKeyConv, numberKeyInConv},
	// ISCSI_PARAM_PDU_INORDER_EN
	"DataPDUInOrder": {IscsiParamPduInorderEn, true, 1, 0, 1, numberKeyConv, numberKeyInConv},
	// ISCSI_PARAM_DATASEQ_INORDER_EN
	"DataSequenceInOrder": {IscsiParamDataseqInorderEn, true, 1, 0, 1, numberKeyConv, numberKeyInConv},
	// ISCSI_PARAM_ERL
	"ErrorRecoveryLevel": {IscsiParamErl, true, 0, 0, 2, numberKeyConv, numberKeyInConv},
	// ISCSI_PARAM_IFMARKER_EN
	"IFMarker": {IscsiParamIfmarkerEn, true, 0, 0, 1, boolKeyConv, boolKeyInConv},
	// ISCSI_PARAM_OFMARKER_EN
	"OFMarker": {IscsiParamOfmarkerEn, true, 0, 0, 1, boolKeyConv, boolKeyInConv},
	// ISCSI_PARAM_DEFAULTTIME2WAIT
	"DefaultTime2Wait": {IscsiParamDefaulttime2wait, true, 2, 0, 3600, numberKeyConv, numberKeyInConv},
	// ISCSI_PARAM_DEFAULTTIME2RETAIN
	"DefaultTime2Retain": {IscsiParamDefaulttime2retain, false, 20, 0, 3600, numberKeyConv, numberKeyInConv},
	// ISCSI_PARAM_OFMARKINT
	"OFMarkInt": {IscsiParamOfmarkint, true, 2048, 1, 65535, numberKeyConv, numberKeyInConv},
	// ISCSI_PARAM_IFMARKINT
	"IFMarkInt": {IscsiParamIfmarkint, true, 2048, 1, 65535, numberKeyConv, numberKeyInConv},
	// ISCSI_PARAM_MAXCONNECTIONS
	"MaxConnections": {IscsiParamMaxconnections, true, 1, 1, 65535, numberKeyConv, numberKeyInConv},
	// ISCSI_PARAM_RDMA_EXTENSIONS
	"RDMAExtensions": {IscsiParamRdmaExtensions, true, 0, 0, 1, boolKeyConv, boolKeyInConv},
	// ISCSI_PARAM_TARGET_RDSL
	"TargetRecvDataSegmentLength": {IscsiParamTargetRdsl, true, 8192, 512, 16777215, numberKeyConv, numberKeyInConv},
	// ISCSI_PARAM_INITIATOR_RDSL
	"InitiatorRecvDataSegmentLength": {IscsiParamInitiatorRdsl, true, 8192, 512, 16777215, numberKeyConv, numberKeyInConv},
	// ISCSI_PARAM_MAX_OUTST_PDU
	"MaxOutstandingUnexpectedPDUs": {IscsiParamMaxOutstPdu, true, 0, 2, 4294967295, numberKeyConv, numberKeyInConv},
	// "local" parmas, never sent to the initiator
	// ISCSI_PARAM_MAX_XMIT_DLENGTH
	"MaxXmitDataSegmentLength": {IscsiParamMaxXmitDlength, true, 8192, 512, 16777215, numberKeyConv, numberKeyInConv},
	// ISCSI_PARAM_MAX_QUEUE_CMD
	"MaxQueueCmd": {IscsiParamMaxQueueCmd, true, MaxQueueCmdDef, MaxQueueCmdMin, MaxQueueCmdMax, numberKeyConv, numberKeyInConv},
}

type ISCSISession struct {
	Initiator      string
	InitiatorAlias string
	Target         *ISCSITarget
	ISID           uint64
	TSIH           uint16
	TPGT           uint16
	SessionType    int
	ITNexus        *scsi.ITNexus

	ExpCmdSN uint32
	MaxCmdSN uint32
	// currently, this is only one connection per session
	Connections        map[uint16]*iscsiConnection
	ConnectionsRWMutex sync.RWMutex
	PendingTasks       taskQueue
	PendingTasksMutex  sync.RWMutex
	MaxQueueCommand    uint32
	SessionParam       ISCSISessionParamList
}

func (targetDriver *ISCSITargetDriver) LookupISCSISession(tgtName string, isid uint64, tsih uint16, tpgt uint16) *ISCSISession {
	tgt, ok := targetDriver.iSCSITargets[tgtName]
	if !ok {
		return nil
	}
	tgt.SessionsRWMutex.RLock()
	defer tgt.SessionsRWMutex.RUnlock()
	session, ok := tgt.Sessions[tsih]
	if !ok {
		return nil
	}
	if (session.ISID == isid) && (session.TPGT == tpgt) {
		return session
	}
	return nil
}

func (targetDriver *ISCSITargetDriver) UnBindISCSISession(session *ISCSISession) {
	target := session.Target
	if target == nil {
		return
	}
	target.SessionsRWMutex.Lock()
	defer target.SessionsRWMutex.Unlock()
	delete(target.Sessions, session.TSIH)
	scsi.RemoveITNexus(session.Target.SCSITarget, session.ITNexus)
}

func (targetDriver *ISCSITargetDriver) BindISCSISession(connection *iscsiConnection) error {
	var (
		target             *ISCSITarget
		existingConnection *iscsiConnection
		newSession         *ISCSISession
		tpgt               uint16
		err                error
	)
	log := logger.GetLogger()
	//Find TPGT and Target ID
	if connection.loginParam.sessionType == SessionDiscovery {
		connection.TargetId = 0xffff
	} else {
		for _, t := range targetDriver.iSCSITargets {
			if t.SCSITarget.Name == connection.loginParam.target {
				target = t
				break
			}
		}
		if target == nil {
			return fmt.Errorf("no target found with name(%s)", connection.loginParam.target)
		}

		tpgt, err = target.TPGT.FindTPG(connection.networkConnection.LocalAddr().String())
		if err != nil {
			return err
		}
		connection.loginParam.tpgt = tpgt
		connection.TargetId = target.TargetId
	}

	existSession := targetDriver.LookupISCSISession(
		connection.loginParam.target,
		connection.loginParam.isid,
		connection.loginParam.tsih,
		connection.loginParam.tpgt,
	)
	if existSession != nil {
		existingConnection = existSession.LookupConnection(connection.ConnectionId)
	}

	if connection.loginParam.sessionType == SessionDiscovery &&
		connection.loginParam.tsih != IscsiUnspecifiedTargetSessionIdentifierHandler &&
		existSession != nil {
		return fmt.Errorf("initiator err, invalid request")
	}

	if existSession == nil && connection.loginParam.tsih != 0 &&
		existSession.TSIH != connection.loginParam.tsih {
		return fmt.Errorf("initiator err, no session")
	}

	if existSession == nil {
		newSession, err = targetDriver.NewISCSISession(connection)
		if err != nil {
			return err
		}

		if newSession.SessionType == SessionNormal {
			log.Infof("Login request received from initiator: %v, Session type: %s, Target name:%v, ISID: 0x%x",
				connection.loginParam.initiator, "Normal", connection.loginParam.target, connection.loginParam.isid)
			//register normal session
			itNexus := &scsi.ITNexus{
				ID:  uuid.NewV1(),
				Tag: GeneraterIscsiItNexusID(newSession)}
			scsi.AddITNexus(newSession.Target.SCSITarget, itNexus)
			newSession.ITNexus = itNexus
			connection.session = newSession

			newSession.Target.SessionsRWMutex.Lock()
			newSession.Target.Sessions[newSession.TSIH] = newSession
			newSession.Target.SessionsRWMutex.Unlock()
		} else {
			log.Infof("Discovery request received from initiator: %v, Session type: %s, ISID: 0x%x",
				connection.loginParam.initiator, "Discovery", connection.loginParam.isid)
			connection.session = newSession
		}
	} else {
		if connection.loginParam.tsih == IscsiUnspecifiedTargetSessionIdentifierHandler {
			log.Infof("Session Reinstatement initiator name:%v,target name:%v,ISID:0x%x",
				connection.loginParam.initiator, connection.loginParam.target, connection.loginParam.isid)
			newSession, err = targetDriver.ReInstatement(existingConnection.session, connection)
			if err != nil {
				return err
			}

			itNexus := &scsi.ITNexus{
				ID:  uuid.NewV1(),
				Tag: GeneraterIscsiItNexusID(newSession),
			}
			scsi.AddITNexus(newSession.Target.SCSITarget, itNexus)
			newSession.ITNexus = itNexus
			connection.session = newSession

			newSession.Target.SessionsRWMutex.Lock()
			newSession.Target.Sessions[newSession.TSIH] = newSession
			newSession.Target.SessionsRWMutex.Unlock()
		} else {
			if existingConnection != nil {
				log.Infof("Connection Reinstatement initiator name:%v,target name:%v,ISID:0x%x",
					connection.loginParam.initiator, connection.loginParam.target, connection.loginParam.isid)
				existingConnection.ReInstatement(connection)
			}
		}
	}

	return nil
}

func (targetDriver *ISCSITargetDriver) NewISCSISession(connection *iscsiConnection) (*ISCSISession, error) {
	var (
		target *ISCSITarget
		tsih   uint16
	)
	for _, t := range targetDriver.iSCSITargets {
		if t.TargetId == connection.TargetId {
			target = t
			break
		}
	}
	if target == nil && connection.TargetId != 0xffff {
		return nil, fmt.Errorf("no target found with TargetId(%d)", connection.TargetId)
	}

	tsih = targetDriver.AllocTSIH()
	if tsih == IscsiUnspecifiedTargetSessionIdentifierHandler {
		return nil, fmt.Errorf("TSIH Pool exhausted TargetId(%d)", connection.TargetId)
	}

	session := &ISCSISession{
		TSIH:            tsih,
		ISID:            connection.loginParam.isid,
		TPGT:            connection.loginParam.tpgt,
		Initiator:       connection.loginParam.initiator,
		InitiatorAlias:  connection.loginParam.initiatorAlias,
		SessionType:     connection.loginParam.sessionType,
		Target:          target,
		Connections:     map[uint16]*iscsiConnection{connection.ConnectionId: connection},
		SessionParam:    connection.loginParam.sessionParam,
		MaxQueueCommand: uint32(connection.loginParam.sessionParam[IscsiParamMaxQueueCmd].Value),
		ExpCmdSN:        connection.expCmdSN,
	}
	return session, nil
}

func (session *ISCSISession) LookupConnection(connectionId uint16) *iscsiConnection {
	session.ConnectionsRWMutex.RLock()
	defer session.ConnectionsRWMutex.RUnlock()
	return session.Connections[connectionId]
}

func (targetDriver *ISCSITargetDriver) ReInstatement(existSess *ISCSISession, conn *iscsiConnection) (*ISCSISession, error) {
	newSess, err := targetDriver.NewISCSISession(conn)
	if err != nil {
		return nil, err
	}
	newSess.ExpCmdSN = existSess.ExpCmdSN
	newSess.MaxCmdSN = existSess.MaxCmdSN + 1
	targetDriver.UnBindISCSISession(existSess)
	for _, tmpConn := range existSess.Connections {
		tmpConn.close()
	}
	existSess.Connections = map[uint16]*iscsiConnection{}
	return newSess, nil
}

func GeneraterIscsiItNexusID(sess *ISCSISession) string {
	//iSCSI I_T nexus identifer = (iSCSI Initiator Name + 'i' + ISID, iSCSI Target Name + 't' + Portal Group Tag)
	strID := fmt.Sprintf("%si0x%12x,%st%d",
		sess.Initiator, sess.ISID,
		sess.Target.SCSITarget.Name,
		sess.TPGT)
	return strID
}
