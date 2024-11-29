// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package iscsi_target

func (iscsiCommand *ISCSICommand) logoutResponseBytes() []byte {
	result := make([]byte, 0, 48)
	result = append(
		result,
		byte(OpLogoutResp),     // Logout response
		0x80,                   // reserved
		0x00,                   // response
		0x00,                   // reserved
		0x00, 0x00, 0x00, 0x00, // 1 byte total AHS, 3 bytes data segment length
		// all zeroes according to rfc
		0x00, 0x00, 0x00, 0x00, // reserved
		0x00, 0x00, 0x00, 0x00, // reserved
	)
	result = append(result, MarshalUint32(iscsiCommand.TaskTag)...) // Initiator Task Tag
	result = append(result, 0x00, 0x00, 0x00, 0x00)                 // reserved
	result = append(result, MarshalUint32(iscsiCommand.StatSN)...)
	result = append(result, MarshalUint32(iscsiCommand.ExpCmdSN)...)
	result = append(result, MarshalUint32(iscsiCommand.MaxCmdSN)...)
	result = append(
		result,
		0x00, 0x00, 0x00, 0x00, // reserved
		0x00, 0x00, 0x00, 0x00, //Time2Wait 2 byte | Time2Retain 2 byte
		0x00, 0x00, 0x00, 0x00, // reserved
		0x00, 0x00, 0x00, 0x00, // Header-Digest (Optional)
	)
	return result
}
