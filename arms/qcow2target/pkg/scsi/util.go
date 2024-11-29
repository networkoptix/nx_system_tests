// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package scsi

import "encoding/binary"

func MarshalUint64(value uint64) []byte {
	result := make([]byte, 8)
	binary.BigEndian.PutUint64(result, value)
	return result
}

func MarshalUint32(value uint32) []byte {
	result := make([]byte, 4)
	binary.BigEndian.PutUint32(result, value)
	return result
}

func StringToByte(line string, align int, maxlength int) []byte {
	lineBytes := []byte(line)
	length := len(lineBytes)
	paddingSize := align - (length % align)

	if (length + paddingSize) > maxlength {
		return lineBytes[0:maxlength]
	} else {
		result := make([]byte, length+paddingSize)
		copy(result, lineBytes)
		return result
	}
}
