// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package qcow2

import (
	"encoding/binary"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
)

type unsignedInt interface {
	uint8 | uint16 | uint32 | uint64
}

func divRoundUp[T unsignedInt](dividend, divisor T) T {
	return (dividend + divisor - 1) / divisor
}

func readUint64At(file io.ReaderAt, address uint64) (uint64, error) {
	var toConvert [8]byte
	_, err := file.ReadAt(toConvert[:], int64(address))
	if err != nil {
		return 0, err
	}
	return binary.BigEndian.Uint64(toConvert[:]), nil
}

func writeUint64At(file io.WriterAt, value, address uint64) error {
	var toConvert [8]byte
	binary.BigEndian.PutUint64(toConvert[:], value)
	_, err := file.WriteAt(toConvert[:], int64(address))
	return err
}

func readUint16At(file io.ReaderAt, address uint64) (uint16, error) {
	var toConvert [2]byte
	_, err := file.ReadAt(toConvert[:], int64(address))
	if err != nil {
		return 0, err
	}
	return binary.BigEndian.Uint16(toConvert[:]), nil
}

func writeUint16At(file io.WriterAt, value uint16, address uint64) error {
	var toConvert [2]byte
	binary.BigEndian.PutUint16(toConvert[:], value)
	_, err := file.WriteAt(toConvert[:], int64(address))
	return err
}

func uint16ToByte(toConvert uint16) []byte {
	buffer := make([]byte, 2)
	binary.BigEndian.PutUint16(buffer, toConvert)
	return buffer
}

func uint32ToByte(toConvert uint32) []byte {
	buffer := make([]byte, 4)
	binary.BigEndian.PutUint32(buffer, toConvert)
	return buffer
}

func uint64ToByte(toConvert uint64) []byte {
	buffer := make([]byte, 8)
	binary.BigEndian.PutUint64(buffer, toConvert)
	return buffer
}

func getClusterSize(clusterBits uint32) uint64 {
	return uint64(1 << clusterBits)
}

func formatDiskSize(size uint64) string {

	value := float64(size)
	for _, prefix := range []string{"B", "KB", "MB", "GB", "TB", "PB"} {
		if uint64(value)/1024 == 0 {
			measuredSize := fmt.Sprintf("%.2f", value)
			measuredSize = strings.TrimRight(
				strings.TrimRight(measuredSize, "0"), ".")
			return fmt.Sprintf("%s%s", measuredSize, prefix)
		}
		value /= 1024
	}
	measuredSize := fmt.Sprintf("%.2f", value)
	measuredSize = strings.TrimRight(
		strings.TrimRight(measuredSize, "0"), ".")
	return fmt.Sprintf("%s%s", measuredSize, "EB")
}

func PathExists(path string) (bool, error) {
	_, err := os.Stat(path)
	if err == nil {
		return true, nil
	}
	if os.IsNotExist(err) {
		return false, nil
	}
	return false, err
}

func offsetIsClusterBoundary(offset uint64, clusterSize uint64) error {
	if offset&(clusterSize-1) != 0 {
		return newErrOffsetIsNotAClusterBoundary(offset, clusterSize)
	}
	return nil
}

func checkAddUint64Boundaries(first, second uint64) error {
	maxUint64 := ^uint64(0)
	if maxUint64-first < second {
		return fmt.Errorf(
			"sum of values %d and %d overflow uint64 boundarie",
			first,
			second,
		)
	}
	return nil
}

func trimBackslash(path string) string {
	if path[len(path)-1] == '/' {
		return path[:len(path)-1]
	}
	return path
}
func isSubDirectory(filePath, dir string) bool {
	if !filepath.IsAbs(filePath) {
		return false
	}
	for filepath.Dir(filePath) != filePath {
		if filePath == trimBackslash(dir) {
			return true
		}
		filePath = filepath.Dir(filePath)
	}
	return false
}
