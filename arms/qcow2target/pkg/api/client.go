// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package api

import (
	"bufio"
	"encoding/json"
	"fmt"
	"net"
	"strings"
)

type ErrApiRequestFailed struct {
	errorMessage string
}

func (apiErr ErrApiRequestFailed) Error() string {
	return strings.Replace(
		apiErr.errorMessage, `\n`, "\n", -1)
}

type ErrUnxpectedResponseType struct {
	responseType string
}

func (err ErrUnxpectedResponseType) Error() string {
	return fmt.Sprintf("Unknown response type %s", err.responseType)
}

func unmarshal[T any](response *Response) (*T, error) {
	result := new(T)
	err := json.Unmarshal(response.Result, result)
	if err != nil {
		return nil, err
	}
	return result, nil
}

type ClientRequester struct {
	socketPath string
}

func NewApiRequester() ClientRequester {
	return ClientRequester{
		socketPath: unixSocketPath,
	}
}

func (api ClientRequester) performUnixSocketRequest(data []byte) ([]byte, error) {
	connection, err := net.Dial("unix", api.socketPath)
	if err != nil {
		return nil, err
	}
	_, err = connection.Write(data)
	if err != nil {
		return nil, err
	}
	_, err = connection.Write([]byte("\n"))
	if err != nil {
		return nil, err
	}
	reader := bufio.NewReader(connection)
	delimiter := byte('\n')
	responseBytes, err := reader.ReadBytes(delimiter)
	return responseBytes, err
}

func (api ClientRequester) request(request Request) (*Response, error) {
	data, err := json.Marshal(request)
	if err != nil {
		return nil, err
	}
	responseBytes, err := api.performUnixSocketRequest(data)
	if err != nil {
		return nil, err
	}
	response := &Response{}
	err = json.Unmarshal(responseBytes, response)
	if err != nil {
		return nil, err
	}
	if response.Error != "" {
		return nil, &ErrApiRequestFailed{errorMessage: response.Error}
	}
	return response, nil
}

func specificRequest[ReqType, RespType any](
	api ClientRequester,
	command ReqType,
	typeName string,
) (*RespType, error) {
	jsonCommand, err := json.Marshal(command)
	if err != nil {
		return nil, err
	}
	request := Request{Type: typeName, Command: jsonCommand}
	response, err := api.request(request)
	if err != nil {
		return nil, err
	}
	if response.Type != typeName {
		return nil, &ErrUnxpectedResponseType{responseType: response.Type}
	}
	return unmarshal[RespType](response)
}

func emptyResponseRequest[ReqType any](
	api ClientRequester,
	command ReqType,
	typeName string,
) error {
	jsonCommand, err := json.Marshal(command)
	if err != nil {
		return err
	}
	request := Request{Type: typeName, Command: jsonCommand}
	response, err := api.request(request)
	if err != nil {
		return err
	}
	if response.Type != TypeEmptyResponse {
		return &ErrUnxpectedResponseType{responseType: response.Type}
	}
	return nil
}

func (api ClientRequester) PerformAttach(
	diskPath string,
	targetName string,
) (*AttachResponse, error) {
	command := AttachRequest{
		DiskPath:   diskPath,
		TargetName: targetName,
	}
	result, err := specificRequest[AttachRequest, AttachResponse](
		api,
		command,
		TypeAttach,
	)
	return result, err
}

func (api ClientRequester) PerformDetachLun(
	targetName string,
	logicalUnitId int,
) (*DetachLunResponse, error) {
	if logicalUnitId > 0xff {
		return nil, fmt.Errorf("logical unit id must be < 256")
	}
	command := DetachLunRequest{
		LunId:      byte(logicalUnitId),
		TargetName: targetName,
	}
	result, err := specificRequest[DetachLunRequest, DetachLunResponse](
		api,
		command,
		TypeDetachLun,
	)
	return result, err
}

func (api ClientRequester) PerformAddTarget(targetName string) error {
	command := AddTargetRequest{
		TargetName: targetName,
	}
	return emptyResponseRequest[AddTargetRequest](
		api,
		command,
		TypeAddTarget,
	)
}

func (api ClientRequester) PerformDeleteTarget(targetName string) error {
	command := DeleteTargetRequest{
		TargetName: targetName,
	}
	return emptyResponseRequest[DeleteTargetRequest](
		api,
		command,
		TypeDeleteTarget,
	)
}

func (api ClientRequester) PerformClearTarget(targetName string) (*ClearTargetResponse, error) {
	command := ClearTargetRequest{
		TargetName: targetName,
	}
	result, err := specificRequest[ClearTargetRequest, ClearTargetResponse](
		api,
		command,
		TypeClearTarget,
	)
	return result, err
}

func (api ClientRequester) PerformList() (*ListResponse, error) {
	request := Request{Type: TypeList, Command: json.RawMessage{'{', '}'}}
	response, err := api.request(request)
	if err != nil {
		return nil, err
	}
	if response.Type != TypeList {
		return nil, &ErrUnxpectedResponseType{responseType: response.Type}
	}
	return unmarshal[ListResponse](response)
}
