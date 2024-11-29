// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package api

import (
	"bufio"
	"encoding/json"
	"log"
	"net"
	"os"
	"qcow2target/pkg/iscsi_target"
	"qcow2target/pkg/qcow2"
	"strings"
)

const unixSocketPath = "/tmp/qcow2target.sock"

type DemonApiServer struct {
	handler       DemonApiHandler
	socketAddress string
}

func NewApiServer(
	iscsiTargetDriver *iscsi_target.ISCSITargetDriver,
	imageFactory *qcow2.ImageFactory,
) *DemonApiServer {
	return &DemonApiServer{
		handler: DemonApiHandler{
			iscsiTargetDriver: iscsiTargetDriver,
			imageFactory:      imageFactory,
		},
		socketAddress: unixSocketPath,
	}
}

func (server *DemonApiServer) HandleConnection(connection net.Conn) {
	defer func() {
		err := connection.Close()
		if err != nil {
			log.Print(err)
		}
	}()
	reader := bufio.NewReader(connection)
	delimiter := byte('\n')
	requestBytes, err := reader.ReadBytes(delimiter)
	if err != nil {
		log.Print(err)
		return
	}
	request, err := ParseRequest(requestBytes[:len(requestBytes)-1])
	if err != nil {
		log.Print(err)
		errorResponse := ErrorResponse(err)
		server.sendResponse(connection, errorResponse, delimiter)
	}
	response := server.handler.HandleRequest(request)
	server.sendResponse(connection, response, delimiter)
}

func (server *DemonApiServer) sendResponse(connection net.Conn, response Response, delimiter byte) {
	response.Error = strings.Replace(response.Error, "\n", `\n`, -1)
	result, err := json.Marshal(response)
	if err != nil {
		log.Print(err)
		return
	}
	_, err = connection.Write(result)
	if err != nil {
		log.Print(err)
		return
	}
	_, err = connection.Write([]byte{delimiter})
	if err != nil {
		log.Print(err)
		return
	}
}

func (server *DemonApiServer) Run() {
	if err := os.RemoveAll(server.socketAddress); err != nil {
		log.Fatal(err)
	}
	listener, err := net.Listen("unix", server.socketAddress)
	if err != nil {
		log.Fatal("listen error:", err)
	}
	defer func() {
		err := listener.Close()
		if err != nil {
			log.Fatal("close error:", err)
		}
	}()
	for {
		connection, err := listener.Accept()
		if err != nil {
			log.Fatal("accept error:", err)
		}
		go server.HandleConnection(connection)
	}
}
