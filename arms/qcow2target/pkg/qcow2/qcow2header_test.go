// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package qcow2

import (
	"testing"
)

var validHeader = []byte{
	0x51, 0x46, 0x49, 0xfb, // magic
	0x00, 0x00, 0x00, 0x03, // version
	0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, // backing file offset
	0x00, 0x00, 0x00, 0x00, // backing file size
	0x00, 0x00, 0x00, 0x0c, // cluster_bits
	0x00, 0x00, 0x00, 0x20, 0x00, 0x00, 0x00, 0x00, // size
	0x00, 0x00, 0x00, 0x00, // crypt method
	0x00, 0x00, 0x00, 0x00, // L1 size
	0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0x00, 0x00, // L1 table offset
	0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, // refcount table offset
	0x00, 0x00, 0x00, 0x01, // refcount table clusters
	0x00, 0x00, 0x00, 0x00, // nb snapshots
	0x00, 0x00, 0x00, 0x00, 0x00, 0x04, 0x00, 0x00, // snapshots offset
	0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, // incompatible_features
	0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, // compatible_features
	0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, // autoclear_features
	0x00, 0x00, 0x00, 0x04, // refcount_order
	0x00, 0x00, 0x00, 0x68, // header_length
}

func TestValidHeaderParsedCorrectly(t *testing.T) {
	headerData := newFileBuffer(validHeader)
	header, err := imageHeaderFromFile(headerData)
	if err != nil {
		t.Fatalf(
			"While parsing a valid header an error occured %s",
			err,
		)
	}
	if header.versionNumber != 3 {
		t.Errorf("Expected version number 3")
	}
}