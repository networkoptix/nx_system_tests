// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package api

import (
	"encoding/json"
	"fmt"
	"qcow2target/pkg/iscsi_target"
	"qcow2target/pkg/qcow2"
	"sync"
)

type DemonApiHandler struct {
	iscsiTargetDriver *iscsi_target.ISCSITargetDriver
	imageFactory      *qcow2.ImageFactory
	apiLock           sync.Mutex
}

func (handler *DemonApiHandler) Attach(request AttachRequest) (*AttachResponse, error) {
	handler.apiLock.Lock()
	defer handler.apiLock.Unlock()
	logicalUnitId, err := handler.iscsiTargetDriver.AddLun(request.TargetName, request.DiskPath)
	if err != nil {
		return nil, err
	}
	return &AttachResponse{
		LogicalUnitId: logicalUnitId,
	}, nil
}

func (handler *DemonApiHandler) DetachLun(request DetachLunRequest) (*DetachLunResponse, error) {
	handler.apiLock.Lock()
	defer handler.apiLock.Unlock()
	LogicalUnitFilePath, err := handler.iscsiTargetDriver.RemoveLun(request.TargetName, request.LunId)
	if err != nil {
		return nil, err
	}
	return &DetachLunResponse{
		FilePath: LogicalUnitFilePath,
	}, nil
}

func (handler *DemonApiHandler) AddTarget(request AddTargetRequest) error {
	handler.apiLock.Lock()
	defer handler.apiLock.Unlock()
	return handler.iscsiTargetDriver.NewTarget(request.TargetName)
}

func (handler *DemonApiHandler) DeleteTarget(request DeleteTargetRequest) error {
	handler.apiLock.Lock()
	defer handler.apiLock.Unlock()
	return handler.iscsiTargetDriver.DeleteTarget(request.TargetName)
}

func (handler *DemonApiHandler) ClearTarget(request ClearTargetRequest) (*ClearTargetResponse, error) {
	handler.apiLock.Lock()
	defer handler.apiLock.Unlock()
	LogicalUnitFilePaths, err := handler.iscsiTargetDriver.Clear(request.TargetName)
	if err != nil {
		return nil, err
	}
	return &ClearTargetResponse{
		FreedLogicalUnitPaths: LogicalUnitFilePaths,
	}, nil
}

func (handler *DemonApiHandler) ListTargets() ListResponse {
	handler.apiLock.Lock()
	defer handler.apiLock.Unlock()
	response := make(ListResponse)
	for key, value := range handler.iscsiTargetDriver.List() {
		targetRepresentation := TargetRepresentation{
			TargetId:       value.TargetId,
			LogicalUnits:   make([]LunRepresentation, len(value.LogicalUnits)),
			HasConnections: value.HasConnections,
			ITNexus:        value.ITNexus,
		}
		for index, value := range value.LogicalUnits {
			targetRepresentation.LogicalUnits[index] = LunRepresentation{
				LogicalUnitId: value.LogicalUnitId,
				FilePath:      value.FilePath,
			}
		}
		response[key] = targetRepresentation
	}
	return response
}

func (handler *DemonApiHandler) HandleRequest(request *Request) Response {
	response := Response{Type: request.Type}
	switch request.Type {
	case TypeAttach:
		command := &AttachRequest{}
		err := json.Unmarshal(request.Command, command)
		if err != nil {
			return ErrorResponse(err)
		}
		result, err := handler.Attach(*command)
		if err != nil {
			return ErrorResponse(err)
		}
		response.Result, err = json.Marshal(result)
		if err != nil {
			return ErrorResponse(err)
		}
		return response
	case TypeDetachLun:
		command := &DetachLunRequest{}
		err := json.Unmarshal(request.Command, command)
		if err != nil {
			return ErrorResponse(err)
		}
		result, err := handler.DetachLun(*command)
		if err != nil {
			return ErrorResponse(err)
		}
		response.Result, err = json.Marshal(result)
		if err != nil {
			return ErrorResponse(err)
		}
		return response
	case TypeAddTarget:
		command := &AddTargetRequest{}
		err := json.Unmarshal(request.Command, command)
		if err != nil {
			return ErrorResponse(err)
		}
		err = handler.AddTarget(*command)
		if err != nil {
			return ErrorResponse(err)
		}
		return emptyResponse()
	case TypeDeleteTarget:
		command := &DeleteTargetRequest{}
		err := json.Unmarshal(request.Command, command)
		if err != nil {
			return ErrorResponse(err)
		}
		err = handler.DeleteTarget(*command)
		if err != nil {
			return ErrorResponse(err)
		}
		return emptyResponse()
	case TypeClearTarget:
		command := &ClearTargetRequest{}
		err := json.Unmarshal(request.Command, command)
		if err != nil {
			return ErrorResponse(err)
		}
		result, err := handler.ClearTarget(*command)
		if err != nil {
			return ErrorResponse(err)
		}
		response.Result, err = json.Marshal(result)
		if err != nil {
			return ErrorResponse(err)
		}
		return response
	case TypeList:
		var err error
		listDiskResult := handler.ListTargets()
		response.Result, err = json.Marshal(listDiskResult)
		if err != nil {
			return ErrorResponse(err)
		}
		return response
	default:
		return ErrorResponse(fmt.Errorf("unknow request type %s", request.Type))
	}
}

func emptyResponse() Response {
	return Response{Error: "", Result: json.RawMessage{'{', '}'}, Type: TypeEmptyResponse}
}

func ErrorResponse(err error) Response {
	return Response{Error: err.Error(), Result: json.RawMessage{'{', '}'}, Type: TypeEmptyResponse}
}
