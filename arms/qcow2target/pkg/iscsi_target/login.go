// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package iscsi_target

import (
	"fmt"
	"strconv"
	"strings"
)

type iSCSILoginStage byte

type AuthMethod int

const AuthNone = 0

const (
	SecurityNegotiation         iSCSILoginStage = 0
	LoginOperationalNegotiation                 = 1
	FullFeaturePhase                            = 3
)

func (s iSCSILoginStage) String() string {
	switch s {
	case SecurityNegotiation:
		return "Security Negotiation"
	case LoginOperationalNegotiation:
		return "Login Operational Negotiation"
	case FullFeaturePhase:
		return "Full Feature Phase"
	}
	return "Unknown Stage"
}

func loginKVDeclare(conn *iscsiConnection, negotiatedKeyValue *KeyValueList) {
	negotiatedKeyValue.add("TargetPortalGroupTag", strconv.Itoa(int(conn.loginParam.tpgt)))
	negotiatedKeyValue.add(
		"MaxRecvDataSegmentLength",
		strconv.Itoa(int(sessionKeys["MaxRecvDataSegmentLength"].def)),
	)
}

func (connection *iscsiConnection) processSecurityData() error {
	securityKV := ParseIscsiKeyValue(connection.request.RawData)

	for key, val := range securityKV {
		if key == "AuthMethod" {
			// It can be a list.
			vals := strings.Split(val, ",")
			if !stringArrayContains(vals, "None") {
				// TODO: respond with Reject message, rather
				// than terminating TCP connection.
				return fmt.Errorf("client requesting AuthMethod:%s, only support None", val)
			}
			connection.loginParam.tgtNSG = LoginOperationalNegotiation
			connection.loginParam.tgtTrans = true
			connection.loginParam.authMethod = AuthNone
		} else if key == "TargetName" {
			connection.loginParam.target = val
		} else if key == "InitiatorName" {
			connection.loginParam.initiator = val
		}
	}

	return nil
}

func (connection *iscsiConnection) processLoginData() (*KeyValueList, error) {
	var (
		uintVal    uint
		ok         bool
		defSessKey *iscsiSessionKeys
		kvChanges  int
	)
	negotiationKeyValue := newKeyValueList()
	loginKV := ParseIscsiKeyValue(connection.request.RawData)

	for key, val := range loginKV {
		// The MaxRecvDataSegmentLength of initiator
		// is the MaxXmitDataSegmentLength of target
		if key == "MaxRecvDataSegmentLength" {
			defSessKey, ok = sessionKeys["MaxXmitDataSegmentLength"]
			uintVal, ok = defSessKey.conv(val)
			connection.loginParam.sessionParam[defSessKey.idx].Value = uintVal
			continue
		}

		if key == "InitiatorName" {
			connection.loginParam.initiator = val
			continue
		} else if key == "InitiatorAlias" {
			connection.loginParam.initiatorAlias = val
			continue
		} else if key == "TargetName" {
			connection.loginParam.target = val
			continue
		} else if key == "SessionType" {
			if val == "Normal" {
				connection.loginParam.sessionType = SessionNormal
			} else {
				connection.loginParam.sessionType = SessionDiscovery
			}
			continue
		}

		defSessKey, ok = sessionKeys[key]
		if ok {
			uintVal, ok = defSessKey.conv(val)

			//hack here
			if key == "HeaderDigest" || key == "DataDigest" {
				if uintVal == DigestAll {
					uintVal = DigestNone
				}
			}
			if ok {
				if defSessKey.constValue {
					//the Negotiation Key cannot be changed! Uses Target default key
					if uintVal != defSessKey.def {
						kvChanges++
					}
					negotiationKeyValue.add(key, defSessKey.inConv(defSessKey.def))
				} else {
					if (uintVal >= defSessKey.min) && (uintVal <= defSessKey.max) {
						connection.loginParam.sessionParam[defSessKey.idx].Value = uintVal
						negotiationKeyValue.add(key, defSessKey.inConv(uintVal))
					} else {
						// the value out of the acceptable range, Uses target default key
						negotiationKeyValue.add(key, defSessKey.inConv(defSessKey.def))
						kvChanges++
					}
				}
			}
		} else {
			//Unknown Key, reject it
			return nil, fmt.Errorf("unknowen Nego KV [%s:%s]", key, val)
		}
	}

	if kvChanges == 0 {
		if (connection.loginParam.iniNSG == FullFeaturePhase) && connection.loginParam.iniTrans {
			connection.loginParam.tgtNSG = FullFeaturePhase
			connection.loginParam.tgtTrans = true
		} else {
			//Currently, we just reject this kind of cases
			return negotiationKeyValue, fmt.Errorf("reject CurrentStage=%s,NextStage=%s,trans=%t",
				connection.loginParam.iniCSG, connection.loginParam.iniNSG, connection.loginParam.iniTrans)
		}
	} else {
		connection.loginParam.tgtNSG = FullFeaturePhase
		connection.loginParam.tgtTrans = true
	}
	return negotiationKeyValue, nil
}

type iscsiLoginParam struct {
	paramInit bool

	iniCSG   iSCSILoginStage
	iniNSG   iSCSILoginStage
	iniTrans bool
	iniCont  bool

	tgtCSG   iSCSILoginStage
	tgtNSG   iSCSILoginStage
	tgtTrans bool
	tgtCont  bool

	sessionType  int
	sessionParam ISCSISessionParamList
	keyDeclared  bool

	initiator      string
	initiatorAlias string
	target         string
	targetAlias    string

	tpgt uint16
	isid uint64
	tsih uint16

	authMethod AuthMethod
}

func (iscsiCommand *ISCSICommand) loginResponseBytes() []byte {
	stagesAndTransitByte := byte(0x00)
	if iscsiCommand.Transit {
		stagesAndTransitByte |= 0x80
	}
	if iscsiCommand.Continue {
		stagesAndTransitByte |= 0x40
	}
	stagesAndTransitByte |= byte(iscsiCommand.CurrentStage&0xff) << 2
	stagesAndTransitByte |= byte(iscsiCommand.NextStage & 0xff)
	result := []byte{
		byte(OpLoginResp), stagesAndTransitByte,
		0x00, 0x00, 0x00, // version-max, version-active, ahs length

	}
	result = append(result, MarshalUint64(uint64(len(iscsiCommand.RawData)))[5:]...)
	result = append(result, MarshalUint64(iscsiCommand.ISID)[2:]...)
	result = append(result, MarshalUint64(uint64(iscsiCommand.TSIH))[6:]...)
	result = append(result, MarshalUint64(uint64(iscsiCommand.TaskTag))[4:]...)
	// reserved
	result = append(result, 0x00, 0x00, 0x00, 0x00)
	result = append(result, MarshalUint64(uint64(iscsiCommand.StatSN))[4:]...)
	result = append(result, MarshalUint64(uint64(iscsiCommand.ExpCmdSN))[4:]...)
	result = append(result, MarshalUint64(uint64(iscsiCommand.MaxCmdSN))[4:]...)
	result = append(
		result,
		iscsiCommand.StatusClass,
		iscsiCommand.StatusDetail,
		0x00, 0x00,
		0x00, 0x00, 0x00, 0x00,
		0x00, 0x00, 0x00, 0x00,
	)
	result = append(result, alignBytesToBlock(iscsiCommand.RawData, 4)...)
	return result
}
