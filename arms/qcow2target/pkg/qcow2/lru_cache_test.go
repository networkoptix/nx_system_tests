// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package qcow2

import "testing"

func TestLruCacheGet(t *testing.T) {
	cacheMap := newCacheMap[uint8, uint8](5)
	cacheVectorContent := uint8(15)
	err := cacheMap.set(8, vectorCacheFromArray[uint8]([]uint8{cacheVectorContent}))
	if err != nil {
		t.Fatalf("LRU cache set() failed %s", err)
	}
	value, ok := cacheMap.get(8)
	if !ok {
		t.Fatalf("Lru cache get failed")
	}
	if value.data[0] != cacheVectorContent {
		t.Errorf(
			"Invalid value data, expected %d, received %d",
			cacheVectorContent,
			value.data[0],
		)
	}
}

func TestLruCacheSuccessfulEviction(t *testing.T) {
	vc := func(value uint8) VectorCache[uint8] {
		return vectorCacheFromArray[uint8]([]uint8{value})
	}
	stubWriteCb := func(key uint8, value VectorCache[uint8]) error {
		return nil
	}
	assertWriteCb := func(expKey uint8, expValue []uint8) func(uint8, VectorCache[uint8]) error {
		return func(key uint8, value VectorCache[uint8]) error {
			if !assertListsEqual[uint8](value.data, expValue) {
				t.Fatalf("Incorrect cache eviciton value %#v, expected %#v",
					value, expValue,
				)
			}
			if key != expKey {
				t.Fatalf("Incorrect cache eviction key %d, expected %d", key, expKey)
			}
			return nil
		}
	}
	cacheMap := newCacheMap[uint8, uint8](5)
	insert := func(key, value uint8) {
		err := cacheMap.insert(key, vc(value), stubWriteCb)
		if err != nil {
			t.Fatalf("Error while inserting %s", err)
		}
	}
	insertWithEviction := func(key, value, expKey, expValue uint8) {
		err := cacheMap.insert(key, vc(value), assertWriteCb(expKey, []uint8{expValue}))
		if err != nil {
			t.Fatalf("Error while inserting %s", err)
		}
	}
	insert(1, 2)
	insert(2, 3)
	insert(3, 4)
	insert(4, 5)
	insert(5, 6)
	insertWithEviction(6, 7, 1, 2)
	insertWithEviction(7, 8, 3, 4)
	for i := 100; i < 1000; i++ {
		insert(uint8(i), uint8(i+1))
	}
}
