// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package iscsi_target

import (
	"net"
	"qcow2target/pkg/logger"
	"syscall"
	"time"
)

func setKeepaliveParameters(
	connection *net.TCPConn,
	keepAlivePeriod int,
	keepAliveInterval int,
	keepAliveCount int,
) error {
	// keepAlivePeriod - delay between the last received TCP packet and
	// sending ping to the client
	// keepAliveInterval - interval after sending tcp keepalive before connection closes
	// keepAliveCount - count of retry of the tcp keepalive
	err := connection.SetKeepAlive(true)
	if err != nil {
		return err
	}
	err = connection.SetKeepAlivePeriod(time.Second * time.Duration(keepAlivePeriod))
	if err != nil {
		return err
	}
	rawConn, err := connection.SyscallConn()
	if err != nil {
		return err
	}
	var connectionErr error
	err = rawConn.Control(
		func(fdPtr uintptr) {
			// got socket file descriptor. Setting parameters.
			fd := int(fdPtr)
			//Number of probes.
			err := syscall.SetsockoptInt(fd, syscall.IPPROTO_TCP, syscall.TCP_KEEPCNT, keepAliveCount)
			if err != nil {
				connectionErr = err
				return
			}
			//Wait time after an unsuccessful probe.
			err = syscall.SetsockoptInt(fd, syscall.IPPROTO_TCP, syscall.TCP_KEEPINTVL, keepAliveInterval)
			if err != nil {
				connectionErr = err
				return
			}
		})
	if err != nil {
		return err
	}
	if connectionErr != nil {
		return connectionErr
	}
	return nil
}

func StartTcpServer(address net.TCPAddr, handler func(connection *net.TCPConn)) error {
	log := logger.GetLogger()
	listener, err := net.ListenTCP("tcp", &address)
	if err != nil {
		log.Error(err)
		return err
	}
	log.Infof("iSCSI service listening on: %v", listener.Addr())
	for {
		connection, err := listener.AcceptTCP()
		if err != nil {
			log.Error(err)
			continue
		}
		err = setKeepaliveParameters(connection, 60, 5, 2)
		if err != nil {
			log.Error(err)
			err = connection.Close()
			if err != nil {
				log.Error(err)
				continue
			}
			continue
		}
		err = connection.SetNoDelay(true)
		if err != nil {
			log.Error(err)
			err = connection.Close()
			if err != nil {
				log.Error(err)
				continue
			}
			continue
		}
		log.Info("connection establishing at: ", connection.LocalAddr().String())
		// start a new thread to do with this command
		go handler(connection)
	}
}
