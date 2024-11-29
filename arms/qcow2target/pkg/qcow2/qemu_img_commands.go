// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package qcow2

import (
	"bytes"
	"fmt"
	"os/exec"
	"strconv"
)

func qemuImgCommand(args ...string) (string, error) {
	command := exec.Command("qemu-img", args...)
	var stdout, stderr bytes.Buffer
	command.Stdout = &stdout
	command.Stderr = &stderr
	err := command.Run()
	if err != nil {
		return "", fmt.Errorf(
			"error, while executing command, stderr: %s",
			stderr.String(),
		)
	}
	return stdout.String(), nil
}

func createQcow2DiskThroughQemu(diskPath string, size uint64, params ...string) (string, error) {
	arguments := make([]string, 0, 10)
	arguments = append(arguments, "create")
	arguments = append(arguments, "-f")
	arguments = append(arguments, "qcow2")
	for _, param := range params {
		arguments = append(arguments, param)
	}
	arguments = append(arguments, diskPath)
	arguments = append(arguments, strconv.FormatUint(size, 10))
	return qemuImgCommand(arguments...)
}

func createQcow2DiskThroughQemuWithParent(
	diskPath string,
	parentPath string,
	diskSize uint64,
	parentSize uint64,
) (string, error) {
	_, err := createQcow2DiskThroughQemu(
		parentPath,
		parentSize,
	)
	if err != nil {
		return "", fmt.Errorf(
			"while creating a parent disk %s and error occured %s",
			parentPath,
			err,
		)
	}
	return createQcow2DiskThroughQemu(
		diskPath,
		diskSize,
		"-b",
		parentPath,
		"-F",
		"qcow2",
	)
}
