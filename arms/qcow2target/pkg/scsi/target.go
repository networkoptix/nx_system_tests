// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package scsi

import (
	"fmt"
	uuid "github.com/satori/go.uuid"
	"qcow2target/pkg/logger"
	"sync"
)

type availableLunNumbers [256]bool

func (available *availableLunNumbers) nextLun() (byte, error) {
	for index, logicalUnitAvailable := range available {
		if !logicalUnitAvailable {
			continue
		}
		available[index] = false
		return byte(index), nil
	}
	return 0, fmt.Errorf(
		"can't have more than 256 logical " +
			"units allocated to a single target")
}

func (available *availableLunNumbers) deleteLun(lunNumber byte) {
	available[lunNumber] = true
}

func (available *availableLunNumbers) clear() {
	for i := range available {
		available[i] = true
	}
}

type SCSITarget struct {
	Name          string
	TargetId      int
	LID           int
	State         TargetState
	DevicesLock   sync.Mutex
	Devices       map[byte]*LogicalUnit
	LUN0          *LogicalUnit
	availableLuns availableLunNumbers
	ITNexusMutex  sync.Mutex
	ITNexus       map[uuid.UUID]*ITNexus `json:"itnexus"`
}

type TargetRepresentation struct {
	TargetId       int
	LogicalUnits   []LunRepresentation
	HasConnections bool
	ITNexus        []string
}

func (targetService *TargetService) NewSCSITarget(
	tid int,
	name string,
) (*SCSITarget, error) {
	targetService.mutex.RLock()
	var target = &SCSITarget{
		Name:        name,
		TargetId:    tid,
		ITNexus:     make(map[uuid.UUID]*ITNexus),
		DevicesLock: sync.Mutex{},
	}
	targetService.targetByTid[tid] = target
	targetService.targetByName[name] = target
	targetService.targets = append(targetService.targets, target)
	targetService.mutex.RUnlock()
	target.availableLuns.clear()
	target.Devices = make(map[byte]*LogicalUnit)
	target.LUN0 = NewLUN0()
	return target, nil
}

func (targetService *TargetService) DeleteScsiTarget(
	name string,
) error {
	target, ok := targetService.targetByName[name]
	if !ok {
		return fmt.Errorf("target not present")
	}
	if target.hasLogicalUnits() {
		return fmt.Errorf("can't remove target which has logical units attached")
	}
	if target.hasConnections() {
		return fmt.Errorf("can't remove target which has active caonnections")
	}
	delete(targetService.targetByName, name)
	delete(targetService.targetByTid, target.TargetId)
	return nil
}

func (target *SCSITarget) AddLun(logicalUnit *LogicalUnit) (byte, error) {
	target.DevicesLock.Lock()
	LunId, err := target.availableLuns.nextLun()
	if err != nil {
		return 0, err
	}
	target.Devices[LunId] = logicalUnit
	target.DevicesLock.Unlock()
	return LunId, nil
}

func (target *SCSITarget) DetachLun(LogicalUnitId byte) (string, error) {
	target.DevicesLock.Lock()
	lun, ok := target.Devices[LogicalUnitId]
	if !ok {
		return "", fmt.Errorf("logical unit not found")
	}
	path := lun.BackingStorage.GetPath()
	err := lun.BackingStorage.Close()
	if err != nil {
		return "", err
	}
	delete(target.Devices, LogicalUnitId)
	target.availableLuns.deleteLun(LogicalUnitId)
	target.DevicesLock.Unlock()
	return path, nil
}

func (target *SCSITarget) Clear() ([]string, error) {
	result := make([]string, 0, 10)
	if target.hasConnections() {
		return nil, fmt.Errorf("target has active iscsi connection")
	}
	for lunId := range target.Devices {
		LogicalUnitDeviceFilePath, err := target.DetachLun(lunId)
		if err != nil {
			return nil, err
		}
		result = append(result, LogicalUnitDeviceFilePath)
	}
	return result, nil
}

func (target *SCSITarget) hasLogicalUnits() bool {
	return len(target.Devices) > 0
}

func (target *SCSITarget) hasConnections() bool {
	target.ITNexusMutex.Lock()
	defer target.ITNexusMutex.Unlock()
	return len(target.ITNexus) > 0
}

func (target *SCSITarget) itNexusesRepresentation() []string {
	result := make([]string, 0, len(target.ITNexus))
	for _, value := range target.ITNexus {
		if value != nil {
			result = append(result, value.Tag)
		} else {
			// explicitly return nil if any nil value is present
			result = append(result, "nil")
		}
	}
	return result
}

func (target *SCSITarget) Representation() TargetRepresentation {
	targetRepresentation := TargetRepresentation{
		TargetId:       target.TargetId,
		LogicalUnits:   make([]LunRepresentation, 0, 10),
		HasConnections: target.hasConnections(),
		ITNexus:        target.itNexusesRepresentation(),
	}
	for _, device := range target.Devices {
		targetRepresentation.LogicalUnits = append(targetRepresentation.LogicalUnits, device.Representation())
	}
	return targetRepresentation
}

func (target *SCSITarget) GetItNexus(command *SCSICommand) *ITNexus {
	for _, itNexus := range target.ITNexus {
		if uuid.Equal(itNexus.ID, command.ITNexusID) {
			return itNexus
		}
	}
	return nil
}

func AddITNexus(target *SCSITarget, itnexus *ITNexus) bool {
	var ret = true
	target.ITNexusMutex.Lock()
	defer target.ITNexusMutex.Unlock()
	if _, ok := target.ITNexus[itnexus.ID]; !ok {
		target.ITNexus[itnexus.ID] = itnexus
		ret = true
	} else {
		ret = false
	}
	return ret
}

func RemoveITNexus(target *SCSITarget, itnexus *ITNexus) {
	target.ITNexusMutex.Lock()
	defer target.ITNexusMutex.Unlock()
	delete(target.ITNexus, itnexus.ID)
}

func (logicalUnit *LogicalUnit) Reserve(command *SCSICommand) error {
	log := logger.GetLogger()
	if !uuid.Equal(logicalUnit.ReserveID, uuid.Nil) && uuid.Equal(logicalUnit.ReserveID, command.ITNexusID) {
		log.Errorf("already reserved %d, %d", logicalUnit.ReserveID, command.ITNexusID)
		return fmt.Errorf("already reserved")
	}
	logicalUnit.ReserveID = command.ITNexusID
	return nil
}
