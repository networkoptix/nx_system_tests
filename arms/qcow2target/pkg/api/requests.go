// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package api

import "encoding/json"

const (
	TypeEmptyResponse = "EMPTY"
	TypeAttach        = "ATTACH"
	TypeDetachLun     = "DETACHLUN"
	TypeAddTarget     = "ADDTARGET"
	TypeDeleteTarget  = "DELETETARGET"
	TypeClearTarget   = "CLEARTARGET"
	TypeList          = "LIST"
)

type Request struct {
	Type    string          `json:"type"`
	Command json.RawMessage `json:"command"`
}

type DiskCreationInfo struct {
	DiskPath   string `json:"disk_path"`
	DiskParent string `json:"disk_parent"`
	Size       uint64 `json:"size"`
}

type AttachRequest struct {
	DiskPath   string `json:"disk_path"`
	TargetName string `json:"target_name"`
}

type DetachLunRequest struct {
	LunId      byte   `json:"lun_id"`
	TargetName string `json:"target_name"`
}

type AddTargetRequest struct {
	TargetName string `json:"target_name"`
}

type DeleteTargetRequest struct {
	TargetName string `json:"target_name"`
}

type ClearTargetRequest struct {
	TargetName string `json:"target_name"`
}

func ParseRequest(data []byte) (*Request, error) {
	request := &Request{}
	err := json.Unmarshal(data, request)
	if err != nil {
		return nil, err
	}
	return request, nil
}
