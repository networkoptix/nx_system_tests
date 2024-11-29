// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package iscsi_target

import (
	"qcow2target/pkg/scsi"
	"sync"
)

const (
	IostateReceiveBasicHeaderSegment  = 1
	IostateReceiveInitAhs             = 2
	IostateReceiveInitHdigest         = 4
	IostateReceiveData                = 8
	IostateReceiveInitDdigest         = 9
	IostateTransmitBasicHeaderSegment = 13
	IostateTransmitInitAhs            = 14
	IostateTransmitAhs                = 15
	IostateTransmitInitHdigest        = 16
	IostateTransmitInitData           = 18
	IostateTransmitData               = 19
	IostateTransmitInitDdigest        = 20
)

const IscsiOpcodeMask byte = 0x3F

type ISCSIDiscoveryMethod string

type ISCSITarget struct {
	*scsi.SCSITarget
	TPGT *TargetPortGroup
	// TSIH is the key
	Sessions        map[uint16]*ISCSISession
	SessionsRWMutex sync.RWMutex
	NopInterval     int
	NopCount        int
}

func newISCSITarget(target *scsi.SCSITarget, tpg *TargetPortGroup) *ISCSITarget {
	return &ISCSITarget{
		SCSITarget: target,
		TPGT:       tpg,
		Sessions:   make(map[uint16]*ISCSISession),
	}
}
