// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package qcow2

import (
	"bytes"
	"errors"
)

type intCell struct {
	value int64
}

// in-memory buffer which implements io.ReadSeeker
// struct solely for testing purposes
type fileBuffer struct {
	data          []byte
	currentOffset *intCell
}

func newFileBuffer(data []byte) fileBuffer {

	return fileBuffer{data: data, currentOffset: &intCell{value: int64(0)}}
}
func (h fileBuffer) Read(p []byte) (int, error) {
	n, err := bytes.NewBuffer(h.data[h.currentOffset.value:]).Read(p)
	if err == nil {
		if h.currentOffset.value+int64(len(p)) < int64(len(h.data)) {
			h.currentOffset.value += int64(len(p))
		} else {
			h.currentOffset.value = int64(len(h.data))
		}
	}
	return n, nil
}

func (h fileBuffer) Seek(offset int64, whence int) (int64, error) {
	switch whence {
	case 0:
		if offset >= int64(len(h.data)) || offset < 0 {
			return 0, errors.New("invalid Offset")
		} else {
			h.currentOffset.value = offset
			return offset, nil
		}
	case 1:
		newOffset := h.currentOffset.value + offset
		if newOffset >= int64(len(h.data)) || newOffset < 0 {
			return 0, errors.New("invalid Offset")
		} else {
			h.currentOffset.value = newOffset
			return newOffset, nil
		}
	case 2:
		newOffset := int64(len(h.data)) - offset
		if newOffset >= int64(len(h.data)) || newOffset < 0 {
			return 0, errors.New("invalid Offset")
		} else {
			h.currentOffset.value = newOffset
			return newOffset, nil
		}
	default:
		return 0, errors.New("unsupported Seek Method")
	}
}
