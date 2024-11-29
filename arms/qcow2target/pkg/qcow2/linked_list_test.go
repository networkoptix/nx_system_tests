// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package qcow2

import (
	"runtime"
	"testing"
)

func TestLinkedListU64(t *testing.T) {
	linkedList := newLinkedList[uint64]()
	for i := 0; i < 100; i += 1 {
		linkedList.addRear(uint64(i))
	}
	for i := 0; i < 100; i += 1 {
		value, err := linkedList.removeFront()
		if value != uint64(i) {
			t.Errorf(
				"Test failed, order of numbers in linked list is broken, %d != %d",
				value,
				uint64(i),
			)
		}
		if err != nil {
			t.Errorf(
				"Test failed, error on remove received %s",
				err,
			)
		}
	}
	_, err := linkedList.removeFront()
	if err == nil {
		t.Errorf("no error on remove from an empty list")
	}
}

func TestLinkedListU64DoesntLeak(t *testing.T) {
	gb10Size := 10 * 1024 * 1024 * 1024
	linkedList := newLinkedList[uint64]()
	for i := 0; i < gb10Size; i += 1 {
		linkedList.addRear(uint64(1))
		_, err := linkedList.removeFront()
		if err != nil {
			t.Errorf("Error while removing from the front of linked list")
		}
	}
	var m runtime.MemStats
	runtime.ReadMemStats(&m)
	if m.Alloc > uint64(gb10Size/100) {
		t.Errorf(
			"Allocation size=%d is more than 100MB, it is probaby leaking",
			m.Alloc,
		)
	}
}

func assertListsEqual[T comparable](first, second []T) bool {
	if len(first) != len(second) {
		return false
	}
	for i := range first {
		if first[i] != second[i] {
			return false
		}
	}
	return true
}

func TestLinkedListU64RemoveByPointer(t *testing.T) {
	list := newLinkedList[uint64]()
	headAndTailPointer := list.addRear(1)
	_, err := list.removeByPointer(headAndTailPointer)
	if err != nil {
		t.Fatalf("Bad list element removal, error: %s", err)
	}
	list.addRear(1)
	secondElementPointer := list.addRear(2)
	list.addRear(3)
	list.addRear(4)
	tailPointer := list.addRear(5)
	_, err = list.removeByPointer(secondElementPointer)
	if err != nil {
		t.Fatalf("Bad list element removal, error: %s", err)
	}
	expected := []uint64{1, 3, 4, 5}
	if !assertListsEqual(expected, list.content()) {
		t.Fatalf("Incorrect list content")
	}
	expected = []uint64{1, 3, 4}
	_, err = list.removeByPointer(tailPointer)
	if err != nil {
		t.Fatalf("Bad list element removal, error: %s", err)
	}
	if !assertListsEqual(expected, list.content()) {
		t.Fatalf("Bad list tail element removal")
	}
}

func TestLinkedList(t *testing.T) {
	list := newLinkedList[uint8]()

	// Test adding to rear
	cell1 := list.addRear(1)
	if list.size != 1 {
		t.Errorf("Expected list size to be 1, but got %d", list.size)
	}
	if list.tail.value != 1 {
		t.Errorf("Expected tail value to be 1, but got %d", list.tail.value)
	}

	// Test adding multiple elements
	cell2 := list.addRear(2)
	if list.size != 2 {
		t.Errorf("Expected list size to be 2, but got %d", list.size)
	}
	if list.tail.value != 2 {
		t.Errorf("Expected tail value to be 2, but got %d", list.tail.value)
	}

	// Test removing from front
	value, err := list.removeFront()
	if err != nil {
		t.Errorf("Unexpected error: %s", err)
	}
	if value != 1 {
		t.Errorf("Expected value to be 1, but got %d", value)
	}
	if list.size != 1 {
		t.Errorf("Expected list size to be 1, but got %d", list.size)
	}
	if list.head.value != 2 {
		t.Errorf("Expected head value to be 2, but got %d", list.head.value)
	}

	// Test removing by pointer
	value, err = list.removeByPointer(cell2)
	if err != nil {
		t.Errorf("Unexpected error: %s", err)
	}
	if value != 2 {
		t.Errorf("Expected value to be 2, but got %d", value)
	}
	if list.size != 0 {
		t.Errorf("Expected list size to be 0, but got %d", list.size)
	}
	if list.head != nil || list.tail != nil {
		t.Errorf("Expected head and tail to be nil, but got %v, %v", list.head, list.tail)
	}

	// Test removing from empty list
	_, err = list.removeFront()
	if err == nil {
		t.Error("Expected error but got nil")
	}
	if err != nil && err.Error() != "can't remove from an empty list" {
		t.Errorf("Expected error to be 'can't remove from an empty list', but got %s", err)
	}
	_, err = list.removeByPointer(cell1)
	if err == nil {
		t.Error("Expected error but got nil")
	}
	if err != nil && err.Error() != "attempt to delete from an empty list" {
		t.Errorf("Expected error to be 'attempt to delete from an empty list")
	}
}
