// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package qcow2

import (
	"bytes"
	"errors"
	"fmt"
	"os"
	"path"
	"testing"
	"time"
)

func imagePreparedQemuImgDefault(
	t *testing.T,
	diskName string,
	diskSize int,
	testCase func(file *os.File, t *testing.T),
) {
	imagePath := prepareQemuImage(diskName, diskSize, t)
	file, err := os.Open(imagePath)
	if err != nil {
		t.Fatalf("Error while trying to open image file")
	}
	defer func() {
		if err := file.Close(); err != nil {
			t.Fatalf("While closing file, %s", err)
		}
	}()
	testCase(file, t)
}

func TestProhibitRelativePath(t *testing.T) {
	imageFactory := NewImageFactory(true)
	relativePath := "./relativePath"
	var assertionError *NonAbsolutePathError
	_, err := imageFactory.OpenImage(relativePath, 1)
	if !errors.As(err, &assertionError) {
		t.Fatalf("Path is not considered as relative %s", err)
	}
}

func TestCorrectParseQemuImgDefaultDisk(t *testing.T) {
	imagePreparedQemuImgDefault(
		t,
		"good_image_no_default",
		10*1024*1024,
		func(file *os.File, t *testing.T) {
			header, err := imageHeaderFromFile(file)
			if err != nil {
				t.Errorf("%s", err)
			}
			if header.versionNumber != 3 {
				t.Errorf(
					"Header version number must be 3 for compat version 1.1(default), received %d",
					header.versionNumber,
				)
			}
		},
	)
}

func TestValidHeaderParseUnParseNotChangingContent(t *testing.T) {
	headerData := newFileBuffer(validHeader)
	header, err := imageHeaderFromFile(headerData)
	if err != nil {
		t.Fatalf(
			"While parsing a valid header an error occured %s",
			err,
		)
	}
	if !bytes.Equal(header.toByte(), validHeader) {
		t.Errorf("Bytes after parsing and unparsing of QEMU QCOW2 V3 drive missmatch")
	}
}

func TestValidWriteHeaderToFile(t *testing.T) {
	prepareTestDir(testsDir(), t)
	header, err := createHeaderForSizeAndPath(uint64(10*1024*1024), nil)
	if err != nil {
		t.Fatalf("Error while creating default image header for size: %s", err)
	}
	imagePath := path.Join(testsDir(), "image_with_headers_filled.qcow2")
	fileExists, err := PathExists(imagePath)
	if err != nil {
		t.Fatalf("Error while checking for file existance: %s", err)
	}
	if fileExists {
		err = os.Remove(imagePath)
		if err != nil {
			t.Fatalf(
				"Error while removing file %s from previous test: %s",
				imagePath,
				err,
			)
		}
	}
	file, err := os.Create(imagePath)
	if err != nil {
		t.Fatalf("Error while trying to open image file")
	}
	defer func() {
		if err := file.Close(); err != nil {
			t.Fatalf("While closing file, %s", err)
		}
	}()
	err = header.writeToFile(file)
	if err != nil {
		t.Errorf("Failed write header to file with error %s", err)
	}
}

func TestParseHeaderDiskWithParent(t *testing.T) {
	size := 1024 * 1024
	imagePath, parentPath := prepareQemuImageWithParent("image_with_parent", "parent", size, size, t)
	file, err := os.Open(imagePath)
	defer func() {
		if err := file.Close(); err != nil {
			t.Fatalf("While closing file, %s", err)
		}
	}()
	if err != nil {
		t.Fatalf("%s", err)
	}
	header, err := imageHeaderFromFile(file)
	if err != nil {
		t.Fatalf("Error while parsing image's with backing file header %s", err)
	}
	if header.backingFilePath == nil {
		t.Fatalf("Incorrectly parsed backing file path")
	}
	if *header.backingFilePath != parentPath {
		t.Errorf(
			"Expected %s for backing file, received %s",
			parentPath,
			*header.backingFilePath,
		)
	}
}

func checkParseDisk(t *testing.T, useCache bool) {
	imagePath := prepareQemuImage("good_image_no_default", 10*1024*1024, t)
	imageFactory := NewImageFactory(useCache)
	_, err := imageFactory.OpenImage(imagePath, 1)
	if err != nil {
		t.Fatalf("Bad parsing result %s", err)
	}
}

func TestParseDiskUseCache(t *testing.T) {
	checkParseDisk(t, true)
}

func TestParseDiskNoCache(t *testing.T) {
	checkParseDisk(t, false)
}

func TestCreateDiskReadWrite(t *testing.T) {
	imagePath := path.Join(testsDir(), "sample.img")
	prepareTestDir(testsDir(), t)
	deleteDiskIfExists(imagePath, t)
	size := uint64(10 * 1024 * 1024)
	image, err := CachedImageFactory().CreateImage(imagePath, size)
	if err != nil {
		t.Fatalf(
			"Error while creating image %s",
			err,
		)
	}

	for step := uint64(1); step <= size; step *= 2 {
		for offset := uint64(0); offset < size; offset += step {
			sizeToWrite := step
			if size-offset < step {
				sizeToWrite = size - offset
			}
			toWrite := make([]byte, sizeToWrite)
			err := image.WriteAt(offset, toWrite)
			if err != nil {
				t.Errorf(
					"Error while writing to file offset=%d, step=%d; err=%s",
					offset, step, err)
			}
			data, err := image.ReadAt(offset, sizeToWrite)
			if err != nil {
				t.Errorf(
					"Error while reading from file offset=%d, step=%d; err=%s",
					offset, step, err)
			}
			if !bytes.Equal(data, toWrite) {
				t.Errorf("bytes missmatch offset=%d, step=%d", offset, step)
			}
		}
	}
}

func checkDiskWrite(t *testing.T, useCache bool) {
	prepareTestDir(testsDir(), t)
	imagePath := path.Join(testsDir(), "sample.img")
	ok, err := PathExists(imagePath)
	if err != nil {
		t.Fatalf(
			"while trying to check for existense an error occured %s",
			err,
		)
	}
	if ok {
		err = os.Remove(imagePath)
		if err != nil {
			t.Fatalf(
				"while removing previous image file %s an error occured %s",
				imagePath,
				err,
			)
		}
	}
	size := uint64(10 * 1024 * 1024)
	imageFactory := NewImageFactory(useCache)
	image, err := imageFactory.CreateImage(imagePath, size)
	if err != nil {
		t.Fatalf(
			"Error while creating image %s",
			err,
		)
	}
	defer func() {
		err := image.Close()
		if err != nil {
			t.Fatalf("While closing the file an error occured")
		}
	}()

	toWrite := make([]byte, size)
	for index := range toWrite {
		toWrite[index] = 12
	}
	err = image.WriteAt(0, toWrite)
	if err != nil {
		t.Errorf(
			"Error while writing to file err=%s", err)
	}
	err = image.Flush()
	if err != nil {
		t.Fatalf("while flushing data an error occured %s", err)
	}
	err = image.Close()
	if err != nil {
		t.Fatalf("while closing the image an error occured %s", err)
	}
	imageFactory = NewImageFactory(useCache)
	image, err = imageFactory.OpenImage(imagePath, 1)
	if err != nil {
		t.Fatalf("error while reopening the file %s", err)
	}
	data, err := image.ReadAt(0, size)
	if err != nil {
		t.Fatalf("error while reading from the file with unsaved caches %s", err)
	}
	if !bytes.Equal(data, toWrite) {
		t.Fatalf("bytes read and write are not equal %t", useCache)
	}
}

func TestDiskWrite(t *testing.T) {
	checkDiskWrite(t, true)
	checkDiskWrite(t, false)
}

func checkDiskWithParentReadWriteOk(t *testing.T, useCache bool) {
	parentImagePath := path.Join(testsDir(), "parent.img")
	imagePath := path.Join(testsDir(), "sample.img")
	prepareTestDir(testsDir(), t)
	deleteDiskIfExists(imagePath, t)
	deleteDiskIfExists(parentImagePath, t)
	size := uint64(10 * 1024 * 1024)
	imageFactory := NewImageFactory(useCache)
	parentImage, err := imageFactory.CreateImage(parentImagePath, size)
	if err != nil {
		t.Fatalf("error while creating a parent image")
	}
	writeSize := uint64(512)
	bytesToWrite := make([]byte, writeSize)
	for i := range bytesToWrite {
		bytesToWrite[i] = 5
	}
	for offset := uint64(0); offset < size; offset += writeSize * 2 {
		err = parentImage.WriteAt(offset, bytesToWrite)
		if err != nil {
			t.Errorf("Error while writing to a parent image")
		}
	}
	if useCache {
		err = parentImage.Flush()
	}
	if err != nil {
		t.Fatalf("Error while flushing a parent image")
	}
	err = parentImage.Close()
	if err != nil {
		t.Fatalf("Error while closing a parent image")
	}
	imageFactory = NewImageFactory(useCache)
	image, err := imageFactory.CreateImageFromBacking(imagePath, parentImagePath)
	if err != nil {
		t.Fatalf("error while creating image from backing file")
	}
	defer func() {
		if err := image.Close(); err != nil {
			t.Fatalf("While closing file, %s", err)
		}
	}()
	defaultBytesToRead := make([]byte, writeSize)
	bytesToWriteToChild := make([]byte, writeSize)
	for i := range bytesToWriteToChild {
		bytesToWriteToChild[i] = 19
	}
	counter := 0
	for offset := uint64(0); offset < size; offset += writeSize {

		data, err := image.ReadAt(offset, writeSize)
		if err != nil {
			t.Fatalf("Error while reading from disk with a parent")
		}
		if counter%2 == 0 {
			if !bytes.Equal(data, bytesToWrite) {
				t.Errorf("Wrong data which is read from backing")
			}
		} else {
			if !bytes.Equal(data, defaultBytesToRead) {
				t.Errorf("Bytes which are read from file are not zeroed")
			}
		}
		counter += 1
	}
}

func TestDiskWithParentReadWrite(t *testing.T) {
	checkDiskWithParentReadWriteOk(t, true)
	checkDiskWithParentReadWriteOk(t, false)
}

func benchImageWrite(t *testing.T, size uint64, useCache bool, blockSize uint64) {
	imagePath := path.Join(testsDir(), "sample.img")
	prepareTestDir(testsDir(), t)
	deleteDiskIfExists(imagePath, t)
	imageFactory := NewImageFactory(useCache)
	image, err := imageFactory.CreateImage(imagePath, size)
	if err != nil {
		t.Fatalf("error while creating an image")
	}
	toWrite := make([]byte, blockSize)
	for i := range toWrite {
		toWrite[i] = 65
	}
	start := time.Now()
	for i := uint64(0); i < size; i += blockSize {
		err := image.WriteAt(i, toWrite)
		if err != nil {
			t.Fatalf("Error while writing to file %s at %d", err, i)
		}
	}
	elapsed := time.Since(start)
	cacheStr := "cache is used"
	if !useCache {
		cacheStr = "cache is not used"
	}
	fmt.Printf("Write for block size=%d and %s, time=%s\n", blockSize, cacheStr, elapsed)
}
func TestBenchmarkQCow2Format(t *testing.T) {
	for blockSize := uint64(512); blockSize <= uint64(1024*1024*1024); blockSize *= 8 {
		benchImageWrite(t, uint64(3*1024*1024*1024), true, blockSize)
		benchImageWrite(t, uint64(3*1024*1024*1024), false, blockSize)
	}
}

func TestBenchmarkQcow2LargeDisk(t *testing.T) {
	blockSize := uint64(2 * 1024 * 1024)
	diskSize := uint64(10 * 1024 * 1024 * 1024)
	benchImageWrite(t, diskSize, true, blockSize)
	benchImageWrite(t, diskSize, false, blockSize)
}

func TestImageWithBackingFileDoNotWriteToBackingFileOnCacheEviction(t *testing.T) {
	clusterSize := 2 << DefaultClusterBits
	uint64Size := 8
	numberOfBytesCanAllocatePerL2Cluster := clusterSize * (clusterSize / uint64Size)
	diskSize := numberOfBytesCanAllocatePerL2Cluster * 3
	baseImagePath := path.Join(testsDir(), "base_image.img")
	prepareTestDir(testsDir(), t)
	deleteDiskIfExists(baseImagePath, t)
	imagePath := path.Join(testsDir(), "image.img")
	deleteDiskIfExists(imagePath, t)
	baseImage, err := NoCacheImageFactory().CreateImage(baseImagePath, uint64(diskSize))
	if err != nil {
		t.Fatalf("Error while creating base image %s", err)
	}
	err = baseImage.WriteAt(0, []byte("1"))
	if err != nil {
		t.Fatalf("Error while writing to the first cluster %s", err)
	}
	err = baseImage.WriteAt(uint64(numberOfBytesCanAllocatePerL2Cluster+1), []byte("1"))
	if err != nil {
		t.Fatalf("Error while writing to the cluster=%d %s", numberOfBytesCanAllocatePerL2Cluster+1, err)
	}
	err = baseImage.WriteAt(uint64(2*numberOfBytesCanAllocatePerL2Cluster+1), []byte("1"))
	if err != nil {
		t.Fatalf("Error while writing to the cluster=%d %s", 2*numberOfBytesCanAllocatePerL2Cluster+1, err)
	}
	err = baseImage.Close()
	if err != nil {
		t.Fatalf("While closing the base image an error occured %s", err)
	}
	childImage, err := ImageFactory{
		useCache:                     true,
		pointerTableCacheSize:        2,
		referenceCountTableCacheSize: 2,
	}.CreateImageFromBacking(imagePath, baseImagePath)
	if err != nil {
		t.Fatalf("Error while creating child image %s", err)
	}
	_, err = childImage.ReadAt(0, childImage.header.clusterSize)
	if err != nil {
		t.Fatalf("Error while reading from a first cluster: %s", err)
	}
	_, err = childImage.ReadAt(uint64(numberOfBytesCanAllocatePerL2Cluster+1), childImage.header.clusterSize)
	if err != nil {
		t.Fatalf("Error while reading from a address=%d: %s", uint64(numberOfBytesCanAllocatePerL2Cluster+1), err)
	}
	// Must be no error at the eviction from the writeback cache
	_, err = childImage.ReadAt(uint64(2*numberOfBytesCanAllocatePerL2Cluster+1), childImage.header.clusterSize)
	if err != nil {
		t.Fatalf("Error while reading from a address=%d: %s", uint64(2*numberOfBytesCanAllocatePerL2Cluster+1), err)
	}
}

func TestHugeFileWrite(t *testing.T) {
	imagePath := path.Join(testsDir(), "sample.img")
	prepareTestDir(testsDir(), t)
	deleteDiskIfExists(imagePath, t)
	imageFactory := NewImageFactory(true)
	gb := uint64(1024 * 1024 * 1024)
	diskSize := uint64(255)
	image, err := imageFactory.CreateImage(imagePath, diskSize*gb)
	if err != nil {
		t.Fatalf("error while creating an image")
	}
	test := func(address, blockSize uint64) {
		toWrite := make([]byte, blockSize)
		for i := range toWrite {
			toWrite[i] = 65
		}
		err := image.WriteAt(address, toWrite)
		if err != nil {
			t.Fatalf("Error while writing to file %s at %d", err, address)
		}
	}
	test(0, 1024)
	test(0, 1024*1024)
	test((diskSize-1)*gb, 1024*1024)
	test(diskSize*gb-1024*1024, 1024*1024)
}
