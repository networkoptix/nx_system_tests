// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package iscsi_target

import (
	"fmt"
	"net"
	"qcow2target/pkg/logger"
	"qcow2target/pkg/scsi"
	"sync"
)

const (
	IscsiMaxTargetSessionIdentifierHandler         = uint16(0xffff)
	IscsiUnspecifiedTargetSessionIdentifierHandler = uint16(0)
)

type ISCSITargetDriver struct {
	SCSI                                   *scsi.TargetService
	Name                                   string
	iSCSITargets                           map[string]*ISCSITarget
	targetPortGroup                        *TargetPortGroup
	TargetSessionIdentifierHandlePool      map[uint16]bool
	TargetSessionIdentifierHandlePoolMutex sync.Mutex
	OpCode                                 int
	blockMultipleHostLogin                 bool
}

func NewISCSITargetDriver(base *scsi.TargetService, portals []string) (*ISCSITargetDriver, error) {
	targetPortGroup, err := newTargetPortGroup(portals)
	if err != nil {
		return nil, err
	}
	driver := &ISCSITargetDriver{
		Name:                              "iscsi",
		iSCSITargets:                      map[string]*ISCSITarget{},
		SCSI:                              base,
		TargetSessionIdentifierHandlePool: map[uint16]bool{0: true, 65535: true},
		targetPortGroup:                   targetPortGroup,
	}
	return driver, nil
}

func (targetDriver *ISCSITargetDriver) AllocTSIH() uint16 {
	var i uint16
	targetDriver.TargetSessionIdentifierHandlePoolMutex.Lock()
	for i = uint16(0); i < IscsiMaxTargetSessionIdentifierHandler; i++ {
		exist := targetDriver.TargetSessionIdentifierHandlePool[i]
		if !exist {
			targetDriver.TargetSessionIdentifierHandlePool[i] = true
			targetDriver.TargetSessionIdentifierHandlePoolMutex.Unlock()
			return i
		}
	}
	targetDriver.TargetSessionIdentifierHandlePoolMutex.Unlock()
	return IscsiUnspecifiedTargetSessionIdentifierHandler
}

func (targetDriver *ISCSITargetDriver) ReleaseTSIH(tsih uint16) {
	targetDriver.TargetSessionIdentifierHandlePoolMutex.Lock()
	delete(targetDriver.TargetSessionIdentifierHandlePool, tsih)
	targetDriver.TargetSessionIdentifierHandlePoolMutex.Unlock()
}

func (targetDriver *ISCSITargetDriver) NewTarget(targetName string) error {
	if _, ok := targetDriver.iSCSITargets[targetName]; ok {
		return fmt.Errorf("target already exists")
	}
	scsiTarget, err := targetDriver.SCSI.NewSCSITarget(len(targetDriver.iSCSITargets), targetName)
	if err != nil {
		return err
	}
	tgt := newISCSITarget(scsiTarget, targetDriver.targetPortGroup)
	targetDriver.iSCSITargets[targetName] = tgt
	return nil
}

func (targetDriver *ISCSITargetDriver) DeleteTarget(targetName string) error {
	if _, ok := targetDriver.iSCSITargets[targetName]; !ok {
		return fmt.Errorf("target does not exist")
	}
	return targetDriver.SCSI.DeleteScsiTarget(targetName)
}

func (targetDriver *ISCSITargetDriver) CheckTargetExists(targetName string) error {
	_, ok := targetDriver.iSCSITargets[targetName]
	if !ok {
		return fmt.Errorf("target does not exist")
	}
	return nil
}

func (targetDriver *ISCSITargetDriver) AddLun(targetName string, diskPath string) (byte, error) {
	target, ok := targetDriver.iSCSITargets[targetName]
	if !ok {
		return 0, fmt.Errorf("target does not exist")
	}
	lun, err := targetDriver.SCSI.LunFactory.NewSCSILu(diskPath)
	if err != nil {
		return 0, err
	}
	lunId, err := target.SCSITarget.AddLun(lun)
	return lunId, err
}

func (targetDriver *ISCSITargetDriver) RemoveLun(targetName string, LogicalUnitId byte) (string, error) {
	target, ok := targetDriver.iSCSITargets[targetName]
	if !ok {
		return "", fmt.Errorf("target does not exist")
	}
	return target.SCSITarget.DetachLun(LogicalUnitId)
}

func (targetDriver *ISCSITargetDriver) Clear(targetName string) ([]string, error) {
	target, ok := targetDriver.iSCSITargets[targetName]
	if !ok {
		return nil, fmt.Errorf("target does not exist")
	}
	return target.SCSITarget.Clear()
}

func (targetDriver *ISCSITargetDriver) List() map[string]scsi.TargetRepresentation {
	result := make(map[string]scsi.TargetRepresentation)
	for targetName, target := range targetDriver.iSCSITargets {
		result[targetName] = target.Representation()
	}
	return result
}

func (targetDriver *ISCSITargetDriver) startNopPingWorker(connection *iscsiConnection) {
	err := connection.probeInitiatorWithPings(5, 1)
	if err != nil {
		if connection.session != nil {
			targetDriver.UnBindISCSISession(connection.session)
		}
		connection.close()
	}
}

func (targetDriver *ISCSITargetDriver) Run() error {
	return StartTcpServer(
		net.TCPAddr{IP: []byte{0, 0, 0, 0}, Port: 3260},
		func(connection *net.TCPConn) {
			iscsiConnection := &iscsiConnection{networkConnection: connection,
				loginParam: &iscsiLoginParam{}}
			iscsiConnection.init()
			iscsiConnection.receiveIOState = IostateReceiveBasicHeaderSegment
			go targetDriver.startNopPingWorker(iscsiConnection)
			// start a new thread to do with this command
			targetDriver.handler(DataIn, iscsiConnection)
		},
	)
}

func (targetDriver *ISCSITargetDriver) handler(events byte, connection *iscsiConnection) {
	log := logger.GetLogger()
	if events&DataIn != 0 {
		log.Debug("rx handler processing...")
		go func() {
			targetDriver.receiveHandler(connection)
			if connection.state == ConnectionStateClose {
				log.Warningf("iscsi connection[%d] closed", connection.ConnectionId)
				if connection.session != nil {
					targetDriver.UnBindISCSISession(connection.session)
				}
				connection.close()
			}
		}()
	}
	if connection.state != ConnectionStateClose && events&DataOut != 0 {
		log.Debug("transfer handler processing...")
		targetDriver.transferHandler(connection)
	}
	if connection.state == ConnectionStateClose {
		log.Warningf("iscsi connection[%d] closed", connection.ConnectionId)
		if connection.session != nil {
			targetDriver.UnBindISCSISession(connection.session)
		}
		connection.close()
	}
}

func (targetDriver *ISCSITargetDriver) receiveHandler(connection *iscsiConnection) {
	var (
		hdigest uint = 0
		ddigest uint = 0
		final        = false
	)
	log := logger.GetLogger()
	connection.readLock.Lock()
	defer connection.readLock.Unlock()
	if connection.state == ConnectionStateScsi {
		hdigest = connection.loginParam.sessionParam[IscsiParamHdrdgstEn].Value & DigestCrc32c
		ddigest = connection.loginParam.sessionParam[IscsiParamDatadgstEn].Value & DigestCrc32c
	}
	for !final {
		switch connection.receiveIOState {
		case IostateReceiveBasicHeaderSegment:
			_final, err := connection.readHeader()
			if err != nil {
				return
			}
			if _final {
				final = true
			}
		case IostateReceiveInitAhs:
			connection.receiveIOState = IostateReceiveData
			break
			if hdigest != 0 {
				connection.receiveIOState = IostateReceiveInitHdigest
			}
		case IostateReceiveData:
			if ddigest != 0 {
				connection.receiveIOState = IostateReceiveInitDdigest
			}
			if connection.request == nil {
				return
			}
			dl := ((connection.request.DataLen + DataPadding - 1) / DataPadding) * DataPadding
			connection.request.RawData = make([]byte, dl)
			length := 0
			for length < dl {
				l, err := connection.readData(connection.request.RawData[length:])
				if err != nil {
					log.Error("read data failed:", err)
					connection.state = ConnectionStateClose
					return
				}
				length += l
			}
			if length != dl {
				log.Debugf("get length is %d, but expected %d", length, dl)
				log.Warning("set connection to close")
				connection.state = ConnectionStateClose
				return
			}
			final = true
		default:
			log.Errorf("error %d %d\n", connection.state, connection.receiveIOState)
			return
		}
	}

	if connection.state == ConnectionStateScsi {
		targetDriver.scsiCommandHandler(connection)
	} else {
		connection.transferIOState = IostateTransmitBasicHeaderSegment
		connection.response = &ISCSICommand{}
		switch connection.request.OperationCode {
		case OpLoginReq:
			log.Debug("OpLoginReq")
			if err := targetDriver.iscsiExecLogin(connection); err != nil {
				log.Error(err)
				log.Warningf("set connection to close")
				connection.state = ConnectionStateClose
			}
		case OpLogoutReq:
			log.Debug("OpLogoutReq")
			if err := iscsiExecLogout(connection); err != nil {
				log.Warningf("set connection to close")
				connection.state = ConnectionStateClose
			}
		case OpTextReq:
			log.Debug("OpTextReq")
			if err := targetDriver.iscsiExecText(connection); err != nil {
				log.Warningf("set connection to close")
				connection.state = ConnectionStateClose
			}
		default:
			iscsiExecReject(connection)
		}
		log.Debugf("connection state is %v", connection.State())
		targetDriver.handler(DataOut, connection)
	}
}

func (targetDriver *ISCSITargetDriver) iscsiExecLogin(connection *iscsiConnection) error {
	connection.ConnectionId = connection.request.ConnID
	connection.loginParam.iniCSG = connection.request.CurrentStage
	connection.loginParam.iniNSG = connection.request.NextStage
	connection.loginParam.iniCont = connection.request.Continue
	connection.loginParam.iniTrans = connection.request.Transit
	connection.loginParam.isid = connection.request.ISID
	connection.loginParam.tsih = connection.request.TSIH
	connection.expCmdSN = connection.request.CmdSN
	connection.maxBurstLength = MaxBurstLength
	connection.maxRecvDataSegmentLength = MaxRecvDataSegmentLength
	connection.maxSeqCount = connection.maxBurstLength / connection.maxRecvDataSegmentLength

	if connection.loginParam.iniCSG == SecurityNegotiation {
		if err := connection.processSecurityData(); err != nil {
			return err
		}
		connection.state = ConnectionStateLogin
		return connection.buildResponsePackage(OpLoginResp, nil)
	}

	if _, err := connection.processLoginData(); err != nil {
		return err
	}

	if !connection.loginParam.paramInit {
		if err := targetDriver.BindISCSISession(connection); err != nil {
			connection.state = ConnectionStateExit
			return err
		}
		connection.loginParam.paramInit = true
	}
	if connection.loginParam.tgtNSG == FullFeaturePhase &&
		connection.loginParam.tgtTrans {
		connection.state = ConnectionStateLoginFull
	} else {
		connection.state = ConnectionStateLogin
	}

	return connection.buildResponsePackage(OpLoginResp, nil)
}

func iscsiExecLogout(connection *iscsiConnection) error {
	log := logger.GetLogger()
	log.Infof("Logout request received from initiator: %v", connection.networkConnection.RemoteAddr().String())
	command := connection.request
	connection.response = &ISCSICommand{
		OperationCode: OpLogoutResp,
		StatSN:        command.ExpStatSN,
		TaskTag:       command.TaskTag,
	}
	if connection.session == nil {
		connection.response.ExpCmdSN = command.CmdSN
		connection.response.MaxCmdSN = command.CmdSN
	} else {
		connection.response.ExpCmdSN = connection.session.ExpCmdSN
		connection.response.MaxCmdSN = connection.session.ExpCmdSN + connection.session.MaxQueueCommand
	}
	return nil
}

func (targetDriver *ISCSITargetDriver) iscsiExecText(connection *iscsiConnection) error {
	log := logger.GetLogger()
	result := newKeyValueList()
	cmd := connection.request
	keys := ParseIscsiKeyValue(cmd.RawData)
	if st, ok := keys["SendTargets"]; ok {
		if st == "All" {
			for name, tgt := range targetDriver.iSCSITargets {
				log.Debugf("iscsi target: %v", name)
				//log.Debugf("iscsi target portals: %v", tgt.Portals)
				result.add("TargetName", name)
				targetPort, err := tgt.TPGT.GetTPG(connection.networkConnection.LocalAddr().String())
				if err != nil {
					return err
				}
				targetPortString := fmt.Sprintf(
					"%s,%d",
					targetPort.TargetPortName,
					targetPort.RelativeTargetPortID,
				)
				result.add("TargetAddress", targetPortString)
			}
		}
	}

	connection.response = &ISCSICommand{
		OperationCode: OpTextResp,
		Final:         true,
		NextStage:     FullFeaturePhase,
		StatSN:        cmd.ExpStatSN,
		TaskTag:       cmd.TaskTag,
		ExpCmdSN:      cmd.CmdSN,
		MaxCmdSN:      cmd.CmdSN,
	}
	connection.response.RawData = UnparseIscsiKeyValue(result)
	return nil
}

func iscsiExecNoopOut(connection *iscsiConnection) error {
	return connection.buildResponsePackage(OpNoopIn, nil)
}

func iscsiExecReject(connection *iscsiConnection) error {
	return connection.buildResponsePackage(OpReject, nil)
}

func iscsiExecR2T(connection *iscsiConnection) error {
	return connection.buildResponsePackage(OpReady, nil)
}

func (targetDriver *ISCSITargetDriver) transferHandler(connection *iscsiConnection) {
	log := logger.GetLogger()
	var (
		hdigest uint   = 0
		ddigest uint   = 0
		offset  uint32 = 0
		final          = false
		count   uint32 = 0
	)
	if connection.state == ConnectionStateScsi {
		hdigest = connection.loginParam.sessionParam[IscsiParamHdrdgstEn].Value & DigestCrc32c
		ddigest = connection.loginParam.sessionParam[IscsiParamDatadgstEn].Value & DigestCrc32c
	}
	if connection.state == ConnectionStateScsi && connection.txTask == nil {
		err := targetDriver.scsiCommandHandler(connection)
		if err != nil {
			log.Error(err)
			return
		}
	}
	response := connection.response
	segmentLen := connection.maxRecvDataSegmentLength
	transferLen := len(response.RawData)
	response.DataSequenceNumber = 0
	maxCount := connection.maxSeqCount

	/* send data splitted by segmentLen */
SendRemainingData:
	if response.OperationCode == OpSCSIIn {
		response.BufferOffset = offset
		if int(offset+segmentLen) < transferLen {
			count += 1
			if count < maxCount {
				response.FinalInSeq = false
				response.Final = false
			} else {
				count = 0
				response.FinalInSeq = true
				response.Final = false
			}
			offset = offset + segmentLen
			response.DataLen = int(segmentLen)
		} else {
			response.FinalInSeq = true
			response.Final = true
			response.DataLen = transferLen - int(offset)
		}
	}
	for {
		switch connection.transferIOState {
		case IostateTransmitBasicHeaderSegment:
			log.Debug("ready to write response")
			log.Debugf("response is %s", response.String())
			if l, err := connection.write(response); err != nil {
				log.Errorf("failed to write data to client: %v", err)
				return
			} else {
				connection.transferIOState = IostateTransmitInitAhs
				log.Debugf("success to write %d length", l)
			}
		case IostateTransmitInitAhs:
			if hdigest != 0 {
				connection.transferIOState = IostateTransmitInitHdigest
			} else {
				connection.transferIOState = IostateTransmitInitData
			}
			if connection.transferIOState != IostateTransmitAhs {
				final = true
			}
		case IostateTransmitAhs:
		case IostateTransmitInitData:
			final = true
		case IostateTransmitData:
			if ddigest != 0 {
				connection.transferIOState = IostateTransmitInitDdigest
			}
		default:
			log.Errorf("error %d %d\n", connection.state, connection.transferIOState)
			return
		}

		if final {
			if response.OperationCode == OpSCSIIn && response.Final != true {
				response.DataSequenceNumber++
				connection.transferIOState = IostateTransmitBasicHeaderSegment
				goto SendRemainingData
			} else {
				break
			}
		}
	}

	log.Debugf("connection state: %v", connection.State())
	switch connection.state {
	case ConnectionStateClose, ConnectionStateExit:
		connection.state = ConnectionStateClose
	case ConnectionStateLogin:
		connection.receiveIOState = IostateReceiveBasicHeaderSegment
		targetDriver.handler(DataIn, connection)
	case ConnectionStateLoginFull:
		if connection.session.SessionType == SessionNormal {
			connection.state = ConnectionStateScsi
		} else {
			connection.state = ConnectionStateFullFeature
		}
		connection.receiveIOState = IostateReceiveBasicHeaderSegment
		targetDriver.handler(DataIn, connection)
	case ConnectionStateScsi:
		connection.txTask = nil
	default:
		log.Warnf("unexpected connection state: %v", connection.State())
		connection.receiveIOState = IostateReceiveBasicHeaderSegment
		targetDriver.handler(DataIn, connection)
	}
}

func (targetDriver *ISCSITargetDriver) scsiCommandHandler(connection *iscsiConnection) (err error) {
	log := logger.GetLogger()
	request := connection.request
	switch request.OperationCode {
	case OpSCSICmd:
		log.Debugf("SCSI Command processing...")
		relTargetPortId := connection.session.TPGT
		portName, err := connection.session.Target.TPGT.FindTargetPortName(relTargetPortId)
		var targetPortName string
		if err != nil {
			targetPortName = "emptytarget"
		} else {
			targetPortName = *portName
		}
		scsiCommand := &scsi.SCSICommand{
			ITNexusID:         connection.session.ITNexus.ID,
			SCB:               request.CDB,
			SCBLength:         len(request.CDB),
			LogicalUnit:       request.LUN,
			Tag:               uint64(request.TaskTag),
			RelTargetPortID:   relTargetPortId,
			TargetPortGroupId: connection.session.Target.TPGT.FindTargetGroup(),
			TargetPortName:    targetPortName,
		}
		if request.Read {
			if request.Write {
				scsiCommand.Direction = scsi.DataBidirection
			} else {
				scsiCommand.Direction = scsi.DataRead
			}
		} else {
			if request.Write {
				scsiCommand.Direction = scsi.DataWrite
			}
		}

		task := &iscsiTask{connection: connection, iscsiCommand: connection.request, tag: connection.request.TaskTag, scsiCommand: scsiCommand}
		task.scsiCommand.OperationCode = connection.request.SCSIOpCode
		if scsiCommand.Direction == scsi.DataBidirection {
			task.scsiCommand.Result = scsi.SAMStatCheckCondition.Stat
			scsi.BuildSenseData(task.scsiCommand, scsi.IllegalRequest, scsi.NoAdditionalSense)
			connection.buildResponsePackage(OpSCSIResp, task)
			connection.rxTask = nil
			break
		}
		if request.Write {
			task.r2tCount = int(request.ExpectedDataLen) - request.DataLen
			task.expectedDataLength = int64(request.ExpectedDataLen)
			if !request.Final {
				task.unsolCount = 1
			}
			// new buffer for the data out
			if scsiCommand.OutSDBBuffer == nil {
				blen := int(request.ExpectedDataLen)
				if blen == 0 {
					blen = request.DataLen
				}
				scsiCommand.OutSDBBuffer = &scsi.SCSIDataBuffer{
					Length: uint32(blen),
					Buffer: make([]byte, blen),
				}
			}
			log.Debugf("SCSI write, R2T count: %d, unsol Count: %d, offset: %d", task.r2tCount, task.unsolCount, task.offset)

			if connection.session.SessionParam[IscsiParamImmDataEn].Value == 1 {
				copy(scsiCommand.OutSDBBuffer.Buffer[task.offset:], connection.request.RawData)
				task.offset += connection.request.DataLen
			}
			if task.r2tCount > 0 {
				// prepare to receive more data
				connection.session.ExpCmdSN += 1
				task.state = taskPending
				connection.session.PendingTasksMutex.Lock()
				connection.session.PendingTasks.Push(task)
				connection.session.PendingTasksMutex.Unlock()
				connection.rxTask = task
				if connection.session.SessionParam[IscsiParamInitialR2tEn].Value == 1 {
					iscsiExecR2T(connection)
					break
				} else {
					log.Debugf("Not ready to exec the task")
					connection.receiveIOState = IostateReceiveBasicHeaderSegment
					targetDriver.handler(DataIn, connection)
					return nil
				}
			}
		} else if scsiCommand.InSDBBuffer == nil {
			scsiCommand.InSDBBuffer = &scsi.SCSIDataBuffer{
				Length: request.ExpectedDataLen,
				Buffer: make([]byte, int(request.ExpectedDataLen)),
			}
		}
		task.offset = 0
		connection.rxTask = task
		if err = targetDriver.iscsiTaskQueueHandler(task); err != nil {
			if task.state == taskPending {
				targetDriver.handler(DataIn, connection)
				err = nil
			}
			return err
		} else {
			if scsiCommand.Direction == scsi.DataRead && scsiCommand.SenseBuffer == nil && request.ExpectedDataLen != 0 {
				connection.buildResponsePackage(OpSCSIIn, task)
			} else {
				connection.buildResponsePackage(OpSCSIResp, task)
			}
			connection.rxTask = nil
		}
	case OpSCSITaskReq:
		// task management function
		task := &iscsiTask{connection: connection, iscsiCommand: connection.request, tag: connection.request.TaskTag, scsiCommand: nil}
		connection.rxTask = task
		if err = targetDriver.iscsiTaskQueueHandler(task); err != nil {
			return
		}
	case OpSCSIOut:
		log.Debug("iSCSI Data-out processing...")
		connection.session.PendingTasksMutex.RLock()
		task := connection.session.PendingTasks.GetByTag(connection.request.TaskTag)
		connection.session.PendingTasksMutex.RUnlock()
		if task == nil {
			err = fmt.Errorf("cannot find iSCSI task with tag[%v]", connection.request.TaskTag)
			log.Error(err)
			return
		}
		copy(task.scsiCommand.OutSDBBuffer.Buffer[task.offset:], connection.request.RawData)
		task.offset += connection.request.DataLen
		task.r2tCount = task.r2tCount - connection.request.DataLen
		log.Debugf("Final: %v", connection.request.Final)
		log.Debugf("r2tCount: %v", task.r2tCount)
		if !connection.request.Final {
			log.Debugf("Not ready to exec the task")
			connection.receiveIOState = IostateReceiveBasicHeaderSegment
			targetDriver.handler(DataIn, connection)
			return nil
		} else if task.r2tCount > 0 {
			// prepare to receive more data
			if task.unsolCount == 0 {
				task.r2tSN += 1
			} else {
				task.r2tSN = 0
				task.unsolCount = 0
			}
			connection.rxTask = task
			iscsiExecR2T(connection)
			break
		}
		task.offset = 0
		log.Debugf("Process the Data-out package")
		connection.rxTask = task
		if err = targetDriver.iscsiExecTask(task); err != nil {
			return
		} else {
			connection.buildResponsePackage(OpSCSIResp, task)
			connection.rxTask = nil
			connection.session.PendingTasksMutex.Lock()
			connection.session.PendingTasks.RemoveByTag(connection.request.TaskTag)
			connection.session.PendingTasksMutex.Unlock()
		}
	case OpNoopOut:
		iscsiExecNoopOut(connection)
	case OpLogoutReq:
		connection.txTask = &iscsiTask{connection: connection, iscsiCommand: connection.request, tag: connection.request.TaskTag}
		connection.transferIOState = IostateTransmitBasicHeaderSegment
		iscsiExecLogout(connection)
	case OpTextReq, OpSNACKReq:
		err = fmt.Errorf("cannot handle yet %s", opCodeMap[connection.request.OperationCode])
		log.Error(err)
		return
	default:
		err = fmt.Errorf("unknown op %s", opCodeMap[connection.request.OperationCode])
		log.Error(err)
		return
	}
	connection.receiveIOState = IostateReceiveBasicHeaderSegment
	targetDriver.handler(DataIn|DataOut, connection)
	return nil
}

func (targetDriver *ISCSITargetDriver) iscsiTaskQueueHandler(task *iscsiTask) error {
	log := logger.GetLogger()
	connection := task.connection
	session := connection.session
	command := task.iscsiCommand
	if command.Immediate {
		return targetDriver.iscsiExecTask(task)
	}
	cmdsn := command.CmdSN
	log.Debugf("CmdSN of command is %d", cmdsn)
	if cmdsn == session.ExpCmdSN {
	retry:
		cmdsn += 1
		session.ExpCmdSN = cmdsn
		log.Debugf("session'targetDriver ExpCmdSN is %d", cmdsn)

		log.Debugf("process task(%d)", task.iscsiCommand.CmdSN)
		if err := targetDriver.iscsiExecTask(task); err != nil {
			log.Error(err)
		}
		session.PendingTasksMutex.Lock()
		if session.PendingTasks.Len() == 0 {
			session.PendingTasksMutex.Unlock()
			return nil
		}
		task = session.PendingTasks.Pop()
		command = task.iscsiCommand
		if command.CmdSN != cmdsn {
			session.PendingTasks.Push(task)
			session.PendingTasksMutex.Unlock()
			return nil
		}
		task.state = taskSCSI
		session.PendingTasksMutex.Unlock()
		goto retry
	} else {
		if command.CmdSN < session.ExpCmdSN {
			err := fmt.Errorf("unexpected command serial number: (%d, %d)", command.CmdSN, session.ExpCmdSN)
			log.Error(err)
			return err
		}
		log.Debugf("add task(%d) into task queue", task.iscsiCommand.CmdSN)
		// add this task into queue and set it as a pending task
		session.PendingTasksMutex.Lock()
		task.state = taskPending
		session.PendingTasks.Push(task)
		session.PendingTasksMutex.Unlock()
		return fmt.Errorf("pending")
	}
}

func (targetDriver *ISCSITargetDriver) iscsiExecTask(task *iscsiTask) error {
	log := logger.GetLogger()
	cmd := task.iscsiCommand
	switch cmd.OperationCode {
	case OpSCSICmd, OpSCSIOut:
		task.state = taskSCSI
		// add scsi target process queue
		err := targetDriver.SCSI.AddCommandQueue(task.connection.session.Target.SCSITarget.TargetId, task.scsiCommand)
		if err != nil {
			task.state = 0
		}
		return err
	case OpLogoutReq:

	case OpNoopOut:
		// just do it in iscsi layer
	case OpSCSITaskReq:
		sess := task.connection.session
		switch cmd.TaskFunc {
		case IscsiTmFuncAbortTask:
			sess.PendingTasksMutex.Lock()
			stask := sess.PendingTasks.RemoveByTag(cmd.ReferencedTaskTag)
			sess.PendingTasksMutex.Unlock()
			if stask == nil {
				task.result = IscsiTmfRspNoTask
			} else {
				// abort this task
				log.Debugf("abort the task[%v]", stask.tag)
				if stask.scsiCommand == nil {
					stask.scsiCommand = &scsi.SCSICommand{Result: scsi.SamStatTaskAborted}
				}
				stask.connection = task.connection
				log.Debugf("stask.networkConnection: %#v", stask.connection)
				stask.connection.buildResponsePackage(OpSCSIResp, stask)
				stask.connection.rxTask = nil
				targetDriver.handler(DataOut, stask.connection)
				task.result = IscsiTmfRspComplete
			}
		case IscsiTmFuncAbortTaskSet:
		case IscsiTmFuncLogicalUnitReset:
		case IscsiTmFuncClearAca:
			fallthrough
		case IscsiTmFuncClearTaskSet:
			fallthrough
		case IscsiTmFuncTargetWarmReset, IscsiTmFuncTargetColdReset, IscsiTmFuncTaskReassign:
			task.result = IscsiTmfRspNotSupported
		default:
			task.result = IscsiTmfRspRejected
		}
		// return response to initiator
		return task.connection.buildResponsePackage(OpSCSITaskResp, task)
	}
	return nil
}
