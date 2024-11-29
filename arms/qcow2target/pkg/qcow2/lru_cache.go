// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package qcow2

import "fmt"

type VectorCache[T any] struct {
	data   []T
	_dirty bool
}

// Creates a `VectorCache` that can hold `count` elements.
func newVectorCache[T any](count uint64) VectorCache[T] {
	return VectorCache[T]{
		data:   make([]T, count),
		_dirty: true,
	}
}

// Creates a `VectorCache` from the passed in `vec`.
func vectorCacheFromArray[T any](vec []T) VectorCache[T] {
	return VectorCache[T]{
		data:   vec,
		_dirty: false,
	}
}

func (cache VectorCache[T]) get(index uint64) T {
	return cache.data[index]
}

func (cache *VectorCache[T]) set(index uint64, value T) {
	cache.data[index] = value
	cache._dirty = true
}

// Gets a reference to the underlying vector.
func (cache VectorCache[T]) getValues() []T {
	return cache.data
}

// Mark this cache element as clean.
func (cache *VectorCache[T]) markClean() {
	cache._dirty = false
}

// Returns the number of elements in the vector.
func (cache VectorCache[T]) len() uint64 {
	return uint64(len(cache.data))
}

func (cache VectorCache[T]) dirty() bool {
	return cache._dirty
}

type LruCacheMap[T comparable, P any] struct {
	capacity uint64
	store    map[T]*cacheMapEntry[T, P]
	queue    linkedList[T]
}

type cacheMapEntry[T comparable, P any] struct {
	data              *VectorCache[P]
	linkedListPointer *linkedListCell[T]
}

func newCacheMap[T comparable, P any](capacity uint64) LruCacheMap[T, P] {
	return LruCacheMap[T, P]{
		capacity: capacity,
		store:    make(map[T]*cacheMapEntry[T, P], capacity),
		queue:    newLinkedList[T](),
	}
}

func (cacheMap LruCacheMap[T, P]) containsKey(key T) bool {
	_, ok := cacheMap.store[key]
	return ok
}

func (cacheMap *LruCacheMap[T, P]) get(key T) (*VectorCache[P], bool) {
	value, ok := cacheMap.store[key]
	if !ok {
		return nil, ok
	}
	index, _ := cacheMap.queue.removeByPointer(value.linkedListPointer)
	linkedListEntryPointer := cacheMap.queue.addRear(index)
	cacheMap.store[key] = &cacheMapEntry[T, P]{
		data:              value.data,
		linkedListPointer: linkedListEntryPointer,
	}
	return value.data, ok
}

// Check if the reference block cache is full, and we need to evict.
func (cacheMap *LruCacheMap[T, P]) insert( // todo probably pointers in map are not
	index T, // garbage collected
	block VectorCache[P],
	writeCallback func(T, VectorCache[P]) error,
) error {
	if uint64(len(cacheMap.store)) == cacheMap.capacity {
		toEvict, err := cacheMap.queue.removeFront()
		if err != nil {
			return err
		}
		evicted, ok := cacheMap.store[toEvict]
		if !ok {
			return fmt.Errorf(
				"inconsistent LRU cache,  value to evict %v from queue"+
					" not present in the cache",
				toEvict,
			)
		}
		delete(cacheMap.store, toEvict)
		if evicted.data.dirty() {
			err := writeCallback(toEvict, *evicted.data)
			if err != nil {
				return err
			}
		}
	}
	err := cacheMap.set(index, block)
	return err
}

func (cacheMap *LruCacheMap[T, P]) set(key T, value VectorCache[P]) error {
	if cacheMap.containsKey(key) {
		previousValue, _ := cacheMap.store[key]
		_, err := cacheMap.queue.removeByPointer(previousValue.linkedListPointer)
		if err != nil {
			return err
		}
		listCellPointer := cacheMap.queue.addRear(key)
		cacheMap.store[key] = &cacheMapEntry[T, P]{
			data:              &value,
			linkedListPointer: listCellPointer,
		}
	} else {
		listCellPointer := cacheMap.queue.addRear(key)
		cacheMap.store[key] = &cacheMapEntry[T, P]{
			data:              &value,
			linkedListPointer: listCellPointer,
		}
	}
	return nil
}

func (cacheMap *LruCacheMap[T, P]) remove(key T) error {
	if cacheMap.containsKey(key) {
		value, _ := cacheMap.store[key]
		_, err := cacheMap.queue.removeByPointer(value.linkedListPointer)
		if err != nil {
			return err
		}
		delete(cacheMap.store, key)
	}
	return nil
}
