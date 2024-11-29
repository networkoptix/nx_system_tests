// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package iscsi_target

import (
	"fmt"
	"net"
	"strings"
)

type TargetPort struct {
	RelativeTargetPortID uint16
	TargetPortName       string
}

type TargetPortGroup struct {
	groupId           uint16
	nextId            uint16
	targetPorts       []TargetPort
	targetPortsByName map[string]int
	targetPortsById   map[uint16]int
}

func (tpgt *TargetPortGroup) AddTargetPort(targetPortName string) {
	targetPort := TargetPort{
		RelativeTargetPortID: tpgt.nextId,
		TargetPortName:       targetPortName,
	}
	index := len(tpgt.targetPorts)
	tpgt.targetPorts = append(tpgt.targetPorts, targetPort)
	tpgt.targetPortsByName[targetPortName] = index
	tpgt.targetPortsById[tpgt.nextId] = index
	tpgt.nextId += 1
}

func checkForAllIpv4(targetPortNames []string) (bool, error) {
	// check if array of string is a single
	// IPv4 address with all zeroes
	allIpv4 := false
	for _, portName := range targetPortNames {
		IpAddress := strings.Split(portName, ":")[0]
		if IpAddress == "0.0.0.0" {
			allIpv4 = true
		}
	}
	if allIpv4 && len(targetPortNames) != 1 {
		return false, fmt.Errorf(
			"if one of ip addresses is 0.0.0.0 - other ips must not be present")
	}
	return allIpv4, nil
}

func extractPortFromAllAddressesIpv4(targetPortNames []string) string {
	// len(targetPortNames) must be 1
	return strings.Split(targetPortNames[0], ":")[1]
}
func localAddresses() ([]string, error) {
	result := make([]string, 0, 10)
	interfaces, err := net.Interfaces()
	if err != nil {
		return nil, err
	}
	for _, netInterface := range interfaces {
		addresses, err := netInterface.Addrs()
		if err != nil {
			continue
		}
		for _, address := range addresses {
			if ipAddress, ok := address.(*net.IPNet); ok {
				if ip := ipAddress.IP.To4(); ip != nil {
					result = append(result, ip.String())
				}
			}
		}
	}
	return result, nil
}

func (tpgt *TargetPortGroup) AddTargetPorts(targetPortNames []string) error {
	allAddressesIpv4, err := checkForAllIpv4(targetPortNames)
	if err != nil {
		return err
	}
	if allAddressesIpv4 {
		port := extractPortFromAllAddressesIpv4(targetPortNames)
		portNames, err := localAddresses()
		if err != nil {
			return err
		}
		targetPortNames = make([]string, len(portNames))
		for index, portName := range portNames {
			targetPortNames[index] = portName + ":" + port
		}
	}
	for _, portName := range targetPortNames {
		tpgt.AddTargetPort(portName)
	}
	return nil
}

func (tpgt TargetPortGroup) FindTPG(portal string) (uint16, error) {
	if id, ok := tpgt.targetPortsByName[portal]; ok {
		return tpgt.targetPorts[id].RelativeTargetPortID, nil
	}
	return 0, fmt.Errorf("no TPGT found with IP(%s)", portal)
}

func (tpgt TargetPortGroup) GetTPG(portal string) (*TargetPort, error) {
	if id, ok := tpgt.targetPortsByName[portal]; ok {
		return &tpgt.targetPorts[id], nil
	}
	return nil, fmt.Errorf("no TPGT found with IP(%s)", portal)
}

func (tpgt TargetPortGroup) FindTargetGroup() uint16 {
	return tpgt.groupId
}

func (tpgt TargetPortGroup) FindTargetPortName(relPortID uint16) (*string, error) {
	if id, ok := tpgt.targetPortsById[relPortID]; ok {
		return &tpgt.targetPorts[id].TargetPortName, nil
	}
	return nil, fmt.Errorf("no TPGT found with relative port id (%d)", relPortID)
}

func newTargetPortGroup(ports []string) (*TargetPortGroup, error) {
	tpg := &TargetPortGroup{
		groupId:           0,
		nextId:            1,
		targetPorts:       make([]TargetPort, 0, 10),
		targetPortsByName: make(map[string]int),
		targetPortsById:   make(map[uint16]int),
	}
	err := tpg.AddTargetPorts(ports)
	if err != nil {
		return nil, err
	}
	return tpg, nil
}
