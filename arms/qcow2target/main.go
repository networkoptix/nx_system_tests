// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package main

import (
	"net/http"
	"os"
	"qcow2target/pkg/api"
	"qcow2target/pkg/iscsi_target"
	"qcow2target/pkg/logger"
	"qcow2target/pkg/qcow2"
	"qcow2target/pkg/scsi"
)
import _ "net/http/pprof"

func main() {
	logger.SetLoggingConfig(logger.Info)
	log := logger.GetLogger()
	go func() {
		err := http.ListenAndServe("localhost:6060", nil)
		log.Errorf("Error: %v", err)
	}()

	imageFactory := qcow2.NewImageFactory(true)
	scsiTargetService := scsi.NewSCSITargetService(imageFactory)
	targetDriver, err := iscsi_target.NewISCSITargetDriver(scsiTargetService, []string{"0.0.0.0:3260"})
	if err != nil {
		log.Error(err)
		os.Exit(1)
	}
	apiServer := api.NewApiServer(targetDriver, imageFactory)
	go apiServer.Run()
	err = targetDriver.Run()
	if err != nil {
		log.Error(err)
	}
}
