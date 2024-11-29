// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package qcow2

import "fmt"

type linkedListCell[T any] struct {
	value    T
	next     *linkedListCell[T]
	previous *linkedListCell[T]
}

func newCell[T any](value T) *linkedListCell[T] {
	return &linkedListCell[T]{value: value, next: nil}
}

func (cell *linkedListCell[T]) setNext(next *linkedListCell[T]) {
	cell.next = next
	next.previous = cell
}

type linkedList[T any] struct {
	head *linkedListCell[T]
	size uint64
	tail *linkedListCell[T]
}

func newLinkedList[T any]() linkedList[T] {
	return linkedList[T]{nil, 0, nil}
}

func (list *linkedList[T]) addRear(element T) *linkedListCell[T] {
	cell := newCell[T](element)
	if list.tail == nil {
		list.head = cell
		list.tail = cell
		list.size = 1
		return list.head
	} else {
		list.tail.setNext(cell)
		list.tail = cell
		list.size += 1
		return list.tail
	}
}

func (list *linkedList[T]) removeFront() (T, error) {
	var defaultValue T
	if list.size == 0 {
		return defaultValue, fmt.Errorf("can't remove from an empty list")
	} else if list.size == 1 {
		returnValue := list.head.value
		list.tail = nil
		list.head = nil
		list.size = 0
		return returnValue, nil
	} else {
		returnValue := list.head.value
		list.head = list.head.next
		list.head.previous = nil
		list.size -= 1
		return returnValue, nil
	}
}

func (list *linkedList[T]) removeByPointer(pointer *linkedListCell[T]) (T, error) {
	var defaultValue T
	if list.size == 0 {
		return defaultValue, fmt.Errorf("attempt to delete from an empty list")
	}
	if pointer.next == nil && pointer.previous == nil {
		// head and tail are the same
		if list.size != 1 {
			return defaultValue, fmt.Errorf(
				"broken list, head and tail are the same, but list size is %d",
				list.size,
			)
		}
	}
	if pointer.previous != nil {
		pointer.previous.next = pointer.next
	} else {
		list.head = pointer.next
	}
	if pointer.next != nil {
		pointer.next.previous = pointer.previous
	} else {
		list.tail = pointer.previous
	}
	list.size -= 1
	return pointer.value, nil
}

func (list linkedList[T]) content() []T {
	result := make([]T, list.size)
	index := 0
	if list.size == 0 {
		return result
	}
	for item := list.head; item.next != nil; item = item.next {
		result[index] = item.value
		index += 1
	}
	result[index] = list.tail.value
	return result
}
