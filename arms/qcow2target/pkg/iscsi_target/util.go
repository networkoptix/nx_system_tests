// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package iscsi_target

import (
	"bytes"
	"encoding/binary"
)

// uint64FromByte parses the given slice as a network-byte-ordered integer.  If
// there are more than 8 bytes in data, it overflows.
func uint64FromByte(data []byte) uint64 {
	var out uint64
	for i := 0; i < len(data); i++ {
		out += uint64(data[len(data)-i-1]) << uint(8*i)
	}
	return out
}

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

// ParseIscsiKeyValue parses iSCSI key value data.
func ParseIscsiKeyValue(data []byte) map[string]string {
	result := make(map[string]string)
	splitData := bytes.Split(data, []byte{0})
	for _, keyValuePair := range splitData {
		keyValue := bytes.Split(keyValuePair, []byte("="))
		if len(keyValue) != 2 {
			continue
		}
		result[string(keyValue[0])] = string(keyValue[1])
	}
	return result
}

type KeyValue struct {
	key   string
	value string
}

func (keyValue KeyValue) toByte() []byte {
	return []byte(keyValue.key + "=" + keyValue.value)
}

type KeyValueList struct {
	list []KeyValue
}

func newKeyValueList() *KeyValueList {
	return &KeyValueList{list: []KeyValue{}}
}

func (kVList *KeyValueList) add(key, value string) {
	kVList.list = append(kVList.list, KeyValue{
		key:   key,
		value: value,
	})
}

func (kVList KeyValueList) Length() int {
	return len(kVList.list)
}

func UnparseIscsiKeyValue(kv *KeyValueList) []byte {
	toJoin := make([][]byte, kv.Length())
	i := 0
	for _, keyValue := range kv.list {
		toJoin[i] = keyValue.toByte()
		i += 1
	}
	return bytes.Join(toJoin, []byte{0})
}

func stringArrayContains(array []string, line string) bool {
	for _, lineInArray := range array {
		if lineInArray == line {
			return true
		}
	}
	return false
}

func alignBytesToBlock(data []byte, blockSize int) []byte {
	for len(data)%blockSize != 0 {
		data = append(data, 0x00)
	}
	return data
}
