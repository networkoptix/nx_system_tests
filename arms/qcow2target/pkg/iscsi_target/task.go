// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
// iSCSI task management
package iscsi_target

const (
	IscsiFlagTmFuncMask byte = 0x7F

	// Function values
	// aborts the task identified by the Referenced Task Tag field
	IscsiTmFuncAbortTask = 1
	// aborts all Tasks issued via this session on the logical unit
	IscsiTmFuncAbortTaskSet = 2
	// clears the Auto Contingent Allegiance condition
	IscsiTmFuncClearAca = 3
	// aborts all Tasks in the appropriate task set as defined by the TST field in the Control mode page
	IscsiTmFuncClearTaskSet     = 4
	IscsiTmFuncLogicalUnitReset = 5
	IscsiTmFuncTargetWarmReset  = 6
	IscsiTmFuncTargetColdReset  = 7
	// reassigns connection allegiance for the task identified by the Referenced Task Tag field to this connection, thus resuming the iSCSI exchanges for the task
	IscsiTmFuncTaskReassign = 8

	// Response values
	// Function complete
	IscsiTmfRspComplete = 0x00
	// Task does not exist
	IscsiTmfRspNoTask = 0x01
	// Task management function not supported
	IscsiTmfRspNotSupported = 0x05
	// Function rejected
	IscsiTmfRspRejected = 0xff
)
