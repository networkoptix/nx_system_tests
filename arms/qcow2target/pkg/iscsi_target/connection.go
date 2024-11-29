// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package iscsi_target

import (
	"fmt"
	"io"
	"net"
	"qcow2target/pkg/logger"
	"qcow2target/pkg/scsi"
	"sort"
	"sync"
	"time"
)

const (
	ConnectionStateFree        = 0
	ConnectionStateLogin       = 6
	ConnectionStateLoginFull   = 7
	ConnectionStateFullFeature = 8
	ConnectionStateClose       = 10
	ConnectionStateExit        = 11
	ConnectionStateScsi        = 12
	ConnectionStateInit        = 13
	ConnectionStateStart       = 14
	ConnectionStateReady       = 15
)

const (
	DataIn  byte = 0x01
	DataOut byte = 0x10
)

type nopThreadState byte

const (
	noRequestReceived = nopThreadState(iota)
	waitingForRequest
	waitingForPingResponse
)

type NoOperationCounters struct {
	statusSequenceNumber,
	expectedCommandSequenceNumber,
	maxCommandSequenceNumber,
	targetTransferTag uint32
	lastReceivedRequestTime time.Time
	pingSentTime            time.Time
	state                   nopThreadState
}

type iscsiConnection struct {
	state             int
	authState         int
	session           *ISCSISession
	TargetId          int
	ConnectionId      uint16
	receiveIOState    int
	transferIOState   int
	networkConnection net.Conn

	request  *ISCSICommand
	response *ISCSICommand

	loginParam *iscsiLoginParam

	// StatSN - the status sequence number on this connection
	statusSequenceNumber uint32
	// ExpStatSN - the expected status sequence number on this connection
	expectedStatusSequenceNumber uint32
	// CmdSN - the command sequence number at the target
	cmdSN uint32
	// ExpCmdSN - the next expected command sequence number at the target
	expCmdSN uint32
	// MaxCmdSN - the maximum CmdSN acceptable at the target from this initiator
	maxCmdSN                 uint32
	maxRecvDataSegmentLength uint32
	maxBurstLength           uint32
	maxSeqCount              uint32

	rxTask *iscsiTask
	txTask *iscsiTask

	readLock  *sync.RWMutex
	writeLock *sync.RWMutex
	// Set of counters for ping request
	noOperationCounters NoOperationCounters
	// No Operation mutex
	noOperationCounterMutex *sync.Mutex
	closed                  bool
}

type taskState int

const (
	taskPending taskState = 0
	taskSCSI    taskState = 1
)

type iscsiTask struct {
	tag                uint32
	connection         *iscsiConnection
	iscsiCommand       *ISCSICommand
	scsiCommand        *scsi.SCSICommand
	state              taskState
	expectedDataLength int64
	result             byte

	offset     int
	r2tCount   int
	unsolCount int
	expR2TSN   int

	r2tSN uint32
}

func (connection *iscsiConnection) init() {
	connection.state = ConnectionStateFree
	connection.readLock = new(sync.RWMutex)
	connection.writeLock = new(sync.RWMutex)
	// target transfer tag to start with
	connection.noOperationCounters.targetTransferTag = 0x00
	connection.noOperationCounterMutex = new(sync.Mutex)
	connection.loginParam.sessionParam = []ISCSISessionParam{}
	connection.loginParam.tgtCSG = LoginOperationalNegotiation
	connection.loginParam.tgtNSG = LoginOperationalNegotiation
	for _, param := range sessionKeys {
		connection.loginParam.sessionParam = append(connection.loginParam.sessionParam,
			ISCSISessionParam{idx: param.idx, Value: param.def})
	}
	sort.Sort(connection.loginParam.sessionParam)
}

func (connection *iscsiConnection) readData(buffer []byte) (int, error) {
	length, err := io.ReadFull(connection.networkConnection, buffer)
	if err != nil {
		return -1, err
	}
	return length, nil
}

func (connection *iscsiConnection) write(response *ISCSICommand) (int, error) {
	connection.writeLock.Lock()
	defer connection.writeLock.Unlock()
	connection.noOperationCounterMutex.Lock()
	defer connection.noOperationCounterMutex.Unlock()
	length, err := connection.networkConnection.Write(response.Bytes())
	connection.updateNoOperationCounters(
		connection.response.StatSN+1,
		connection.response.ExpCmdSN,
		connection.response.MaxCmdSN,
	)
	return length, err
}

func (connection *iscsiConnection) close() {
	connection.writeLock.Lock()
	defer connection.writeLock.Unlock()
	if !connection.closed {
		connection.closed = true
		connection.networkConnection.Close()
	}
}

func (connection *iscsiConnection) ReInstatement(newConn *iscsiConnection) {
	connection.close()
	connection.networkConnection = newConn.networkConnection
}

func (connection *iscsiConnection) buildResponsePackage(oc OpCode, task *iscsiTask) error {
	connection.txTask = &iscsiTask{
		connection:   connection,
		iscsiCommand: connection.request,
		tag:          connection.request.TaskTag,
		scsiCommand:  &scsi.SCSICommand{},
	}
	connection.transferIOState = IostateTransmitBasicHeaderSegment
	connection.statusSequenceNumber += 1
	if task == nil {
		task = connection.rxTask
	}
	connection.response = &ISCSICommand{
		StartTime:       connection.request.StartTime,
		StatSN:          connection.request.ExpStatSN,
		TaskTag:         connection.request.TaskTag,
		ExpectedDataLen: connection.request.ExpectedDataLen,
	}
	if connection.session != nil {
		connection.response.ExpCmdSN = connection.session.ExpCmdSN
		connection.response.MaxCmdSN = connection.session.ExpCmdSN + connection.session.MaxQueueCommand
	}
	switch oc {
	case OpReady:
		connection.response.OperationCode = OpReady
		connection.response.R2TSN = task.r2tSN
		connection.response.Final = true
		connection.response.BufferOffset = uint32(task.offset)
		connection.response.DesiredLength = uint32(task.r2tCount)
		if val := connection.loginParam.sessionParam[IscsiParamMaxBurst].Value; task.r2tCount > int(val) {
			connection.response.DesiredLength = uint32(val)
		}
	case OpSCSIIn, OpSCSIResp:
		connection.response.OperationCode = oc
		connection.response.SCSIOpCode = connection.request.SCSIOpCode
		connection.response.Immediate = true
		connection.response.Final = true
		connection.response.SCSIResponse = 0x00
		connection.response.HasStatus = true
		connection.response.Status = task.scsiCommand.Result
		if task.scsiCommand.Result != 0 && task.scsiCommand.SenseBuffer != nil {
			length := MarshalUint32(task.scsiCommand.SenseBuffer.Length)
			connection.response.RawData = append(length[2:4], task.scsiCommand.SenseBuffer.Buffer...)
		} else if task.scsiCommand.Direction == scsi.DataRead || task.scsiCommand.Direction == scsi.DataWrite {
			if task.scsiCommand.InSDBBuffer != nil {
				connection.response.Resid = task.scsiCommand.InSDBBuffer.Residual
				if connection.response.Resid != 0 && connection.response.Resid < task.scsiCommand.InSDBBuffer.Length {
					connection.response.RawData = task.scsiCommand.InSDBBuffer.Buffer[:connection.response.Resid]
				} else {
					connection.response.RawData = task.scsiCommand.InSDBBuffer.Buffer
				}
			} else {
				connection.response.RawData = []byte{}
			}
		}

	case OpNoopIn, OpReject:
		connection.response.OperationCode = oc
		connection.response.Final = true
		connection.response.NextStage = FullFeaturePhase
		connection.response.ExpCmdSN = connection.request.CmdSN + 1
	case OpSCSITaskResp:
		connection.response.OperationCode = oc
		connection.response.Final = true
		connection.response.NextStage = FullFeaturePhase
		connection.response.ExpCmdSN = connection.request.CmdSN + 1
		connection.response.Result = task.result
	case OpLoginResp:
		connection.response.OperationCode = OpLoginResp
		connection.response.Transit = connection.loginParam.tgtTrans
		connection.response.CurrentStage = connection.request.CurrentStage
		connection.response.NextStage = connection.loginParam.tgtNSG
		connection.response.ExpCmdSN = connection.request.CmdSN
		connection.response.MaxCmdSN = connection.request.CmdSN
		if connection.request.CurrentStage != SecurityNegotiation {
			negoKeys, err := connection.processLoginData()
			if err != nil {
				return err
			}
			if !connection.loginParam.keyDeclared {
				loginKVDeclare(connection, negoKeys)
				connection.loginParam.keyDeclared = true
			}
			connection.response.RawData = UnparseIscsiKeyValue(negoKeys)
		}
		connection.txTask = nil
	}

	return nil
}

func (connection *iscsiConnection) State() string {
	switch connection.state {
	case ConnectionStateFree:
		return "free"
	case ConnectionStateLogin:
		return "begin login"
	case ConnectionStateLoginFull:
		return "done login"
	case ConnectionStateFullFeature:
		return "full feature"
	case ConnectionStateClose:
		return "close"
	case ConnectionStateExit:
		return "exit"
	case ConnectionStateScsi:
		return "scsi"
	case ConnectionStateInit:
		return "init"
	case ConnectionStateStart:
		return "start"
	case ConnectionStateReady:
		return "ready"
	}
	return ""
}

func (connection *iscsiConnection) updateNoOperationCounters(
	statusSequenceNumber,
	expectedCommandSequenceNumber,
	maxCommandSequenceNumber uint32,
) {
	connection.noOperationCounters.statusSequenceNumber = statusSequenceNumber
	connection.noOperationCounters.expectedCommandSequenceNumber = expectedCommandSequenceNumber
	connection.noOperationCounters.maxCommandSequenceNumber = maxCommandSequenceNumber
}

func (connection *iscsiConnection) incrementNoOperationTargetTransferTag() {
	connection.noOperationCounters.targetTransferTag += 1
}

func (connection *iscsiConnection) noOpInResponse() []byte {
	result := []byte{
		byte(OpNoopIn),
		// Reserved
		// final bit is set
		0x80, 0x00, 0x00,
		// Total Additional Header Segment length
		0x00,
		// Data Segment Length
		0x00, 0x00, 0x00,
		// Logical Unit Number
		0x00, 0x00, 0x00, 0x00,
		0x00, 0x00, 0x00, 0x00,
		// Initiator task tag
		0xff, 0xff, 0xff, 0xff,
	}
	result = append(
		result,
		MarshalUint32(connection.noOperationCounters.targetTransferTag)...,
	)
	result = append(
		result,
		MarshalUint32(connection.noOperationCounters.statusSequenceNumber)...,
	)
	result = append(
		result,
		MarshalUint32(connection.noOperationCounters.expectedCommandSequenceNumber)...,
	)
	result = append(
		result,
		MarshalUint32(connection.noOperationCounters.maxCommandSequenceNumber)...,
	)
	// Reserved
	result = append(result,
		0x00, 0x00, 0x00, 0x00,
		0x00, 0x00, 0x00, 0x00,
		0x00, 0x00, 0x00, 0x00,
	)
	return result
}

func (connection *iscsiConnection) sendNoOperationPing() error {
	connection.writeLock.Lock()
	defer connection.writeLock.Unlock()
	connection.noOperationCounterMutex.Lock()
	defer connection.noOperationCounterMutex.Unlock()
	if connection.closed {
		return fmt.Errorf("connection already closed")
	}
	response := connection.noOpInResponse()
	_, err := connection.networkConnection.Write(response)
	if err != nil {
		return err
	}
	connection.incrementNoOperationTargetTransferTag()
	connection.noOperationCounters.state = waitingForPingResponse
	connection.noOperationCounters.pingSentTime = time.Now()
	return nil
}

func (connection *iscsiConnection) readHeader() (bool, error) {
	log := logger.GetLogger()
	buffer := make([]byte, BasicHeaderSegmentSize)
	log.Debug("reading header")
	length, err := connection.readData(buffer)
	if err != nil {
		log.Error("read BHS failed:", err)
		connection.state = ConnectionStateClose
		return false, err
	}
	if length == 0 {
		log.Warningf("set connection to close")
		connection.state = ConnectionStateClose
		return false, fmt.Errorf("received empty data, closing the connection")
	}
	iscsiCommand, err := parseHeader(buffer)
	if err != nil {
		log.Error(err)
		log.Warningf("set connection to close")
		connection.state = ConnectionStateClose
		return false, err
	}
	// If initiator task tag is reserved we do not reply
	if iscsiCommand.OperationCode == OpNoopOut && iscsiCommand.TaskTag == 0xffffffff {
		connection.onReceivedHeader()
		return false, nil
	}
	connection.request = iscsiCommand
	if length == BasicHeaderSegmentSize && iscsiCommand.DataLen != 0 {
		connection.receiveIOState = IostateReceiveInitAhs
		connection.onReceivedHeader()
		return false, nil
	}
	log.Debugf("got command: \n%s", iscsiCommand.String())
	log.Debugf("got buffer: %v", buffer)
	connection.onReceivedHeader()
	return true, nil
}

func (connection *iscsiConnection) onReceivedHeader() {
	connection.noOperationCounterMutex.Lock()
	defer connection.noOperationCounterMutex.Unlock()
	connection.noOperationCounters.lastReceivedRequestTime = time.Now()
	connection.noOperationCounters.state = waitingForRequest
}

type ErrInitiatorConnectionTimeout struct{}

func (err ErrInitiatorConnectionTimeout) Error() string {
	return "no heartbeat received"
}

func computeSleepDuration(timeout, sleepDuration time.Duration, futureTimestamp time.Time) time.Duration {
	elapsedTime := time.Now().Sub(futureTimestamp)
	if actualSleepDuration := timeout - elapsedTime; actualSleepDuration < sleepDuration {
		return actualSleepDuration
	}
	return sleepDuration
}

func (connection *iscsiConnection) probeInitiatorWithPings(nopIntervalSeconds, nopTimeoutSeconds int) error {
	sleepDuration := time.Millisecond * 50
	for {
		if connection.session == nil {
			time.Sleep(sleepDuration)
			continue
		}
		if connection.state != ConnectionStateScsi {
			time.Sleep(sleepDuration)
			continue
		}
		if connection.noOperationCounters.state == noRequestReceived {
			time.Sleep(sleepDuration)
			continue
		}
		if connection.noOperationCounters.state == waitingForRequest {
			elapsedTime := time.Now().Sub(connection.noOperationCounters.lastReceivedRequestTime)
			nopInterval := time.Duration(nopIntervalSeconds) * time.Second
			if elapsedTime < nopInterval {
				time.Sleep(
					computeSleepDuration(
						nopInterval,
						sleepDuration,
						connection.noOperationCounters.lastReceivedRequestTime,
					))
				continue
			}
			err := connection.sendNoOperationPing()
			if err != nil {
				return err
			}
		} else if connection.noOperationCounters.state == waitingForPingResponse {
			elapsedTime := time.Now().Sub(connection.noOperationCounters.pingSentTime)
			nopTimeout := time.Duration(nopTimeoutSeconds) * time.Second
			if elapsedTime < nopTimeout {
				time.Sleep(computeSleepDuration(
					nopTimeout,
					sleepDuration,
					connection.noOperationCounters.pingSentTime,
				))
				continue
			}
			return &ErrInitiatorConnectionTimeout{}
		}
	}
}
