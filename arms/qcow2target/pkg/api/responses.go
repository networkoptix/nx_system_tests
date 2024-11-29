// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package api

import (
	"encoding/json"
	"fmt"
	"strings"
)

type Response struct {
	Type   string
	Error  string          `json:"error"`
	Result json.RawMessage `json:"result"`
}

type AttachResponse struct {
	LogicalUnitId byte `json:"lun_id"`
}

func (response AttachResponse) ToCmdlineOutput() string {
	return fmt.Sprintf("Successfully attached disk at lun %d", response.LogicalUnitId)
}

type DetachLunResponse struct {
	FilePath string `json:"file_path"`
}

func (response DetachLunResponse) ToCmdlineOutput() string {
	return fmt.Sprintf("After detaching the logical unit, freed disk '%s'", response.FilePath)
}

type ClearTargetResponse struct {
	FreedLogicalUnitPaths []string `json:"freed_logical_unit_paths"`
}

func (response ClearTargetResponse) ToCmdlineOutput() string {
	paths := make([]string, len(response.FreedLogicalUnitPaths))
	for index, value := range response.FreedLogicalUnitPaths {
		paths[index] = fmt.Sprintf("\t* %s", value)
	}
	return fmt.Sprintf(
		"While clearing target, freed disks:\n%s", strings.Join(paths, "\n"),
	)
}

type LunRepresentation struct {
	LogicalUnitId byte   `json:"logical_unit_id"`
	FilePath      string `json:"file_path"`
}
type TargetRepresentation struct {
	TargetId       int                 `json:"target_id"`
	LogicalUnits   []LunRepresentation `json:"logical_units"`
	HasConnections bool                `json:"has_connections"`
	ITNexus        []string            `json:"it_nexuses"`
}

type ListResponse map[string]TargetRepresentation

func (response ListResponse) ToCmdlineOutput() string {
	result := ""
	result += "Listed targets: \n"
	for targetName, targetRepresentation := range response {
		result += fmt.Sprintf("  Target: %s\n", targetName)
		result += fmt.Sprintf("  Target ID: %d\n", targetRepresentation.TargetId)
		result += fmt.Sprintf("  Has connections: %t\n", targetRepresentation.HasConnections)
		result += "  Luns: \n"
		for _, lu := range targetRepresentation.LogicalUnits {
			result += fmt.Sprintf("    - Lun ID: %d\n", lu.LogicalUnitId)
			result += fmt.Sprintf("      Lun path: %s\n", lu.FilePath)
		}
		result += "  IT Nexuses: \n"
		for index, nexus := range targetRepresentation.ITNexus {
			result += fmt.Sprintf("    - IT Nexus: %s\n", nexus)
			if index != len(targetRepresentation.ITNexus)-1 {
				result += "\n"
			}
		}

	}
	return result
}
