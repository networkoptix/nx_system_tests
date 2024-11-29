// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package main

import (
	"fmt"
	"os"
	"qcow2target/pkg/api"
	"qcow2target/pkg/cli"
	"strconv"
)

type Client struct {
	client   api.ClientRequester
	commands *cli.CommandList
}

func addAttachCli(commands *cli.CommandList) {
	commands.AddCommand(
		CommandAttach,
		" Open qcow2 disk, create logical unit,"+
			" attach logical unit to target.",
	).AddParameter(
		"-d",
		"disk_path",
		"Absolute path to the qcow2 disk.",
		"disk path",
		true,
	).AddParameter(
		"-t",
		"target_name",
		"string iSCSI target name",
		"disk path",
		true,
	)
}

func addDetachLunCli(commands *cli.CommandList) {
	commands.AddCommand(
		CommandDetachLun,
		"Detach logical unit from target by id.",
	).AddParameter(
		"-t",
		"target_name",
		"string iSCSI target name",
		"target name",
		true,
	).AddParameter(
		"-l",
		"lun_id",
		"integer id of logical unit",
		"logical unit id",
		true,
	)
}

func addAddTargetCli(commands *cli.CommandList) {
	commands.AddCommand(
		CommandAddTarget,
		"Create new target if not exists."+
			" If exists - fails.",
	).AddParameter(
		"-t",
		"target_name",
		"string iSCSI target name",
		"target name",
		true,
	)
}

func addDeleteTargetCli(commands *cli.CommandList) {
	commands.AddCommand(
		CommandDeleteTarget,
		"Delete target."+
			" Doesn't work if target has LUNs or "+
			"connected IT nexuses.",
	).AddParameter(
		"-t",
		"target_name",
		"string iSCSI target name",
		"target name",
		true,
	)
}

func addClearTargetCli(commands *cli.CommandList) {
	commands.AddCommand(
		CommandClearTarget,
		"Detach all logical units from target.",
	).AddParameter(
		"-t",
		"target_name",
		"string iSCSI target name",
		"target name",
		true,
	)
}

func addListCli(commands *cli.CommandList) {
	commands.AddCommand(CommandListTargets, "List all targets with logical units")
}

func NewClient() Client {
	commands := cli.NewCommandList(
		"qcow2targetadmin",
		"a tool to communicate with "+
			"qcow2target server\n",
	)
	addAttachCli(commands)
	addDetachLunCli(commands)
	addAddTargetCli(commands)
	addDeleteTargetCli(commands)
	addClearTargetCli(commands)
	addListCli(commands)
	return Client{
		client:   api.NewApiRequester(),
		commands: commands,
	}
}

const (
	CommandAttach       = "attach"
	CommandDetachLun    = "detachlun"
	CommandAddTarget    = "addtarget"
	CommandDeleteTarget = "deletetarget"
	CommandClearTarget  = "cleartarget"
	CommandListTargets  = "list"
)

func (client Client) PerformAttach(command *cli.Command) error {
	targetName, err := command.GetParameter("target_name")
	if err != nil {
		return err
	}
	diskPath, err := command.GetParameter("disk_path")
	if err != nil {
		return err
	}
	response, err := client.client.PerformAttach(diskPath, targetName)
	if err != nil {
		return err
	}
	fmt.Println(response.ToCmdlineOutput())
	return nil
}

func (client Client) PerformDetachLun(command *cli.Command) error {
	targetName, err := command.GetParameter("target_name")
	if err != nil {
		return err
	}
	logicalUnitIdStr, err := command.GetParameter("lun_id")
	if err != nil {
		return err
	}
	lunId, err := strconv.Atoi(logicalUnitIdStr)
	if err != nil {
		return fmt.Errorf("logical unit id must be int, '%s', received", logicalUnitIdStr)
	}
	response, err := client.client.PerformDetachLun(targetName, lunId)
	if err != nil {
		return err
	}
	fmt.Println(response.ToCmdlineOutput())
	return nil
}

func (client Client) PerformAddTarget(command *cli.Command) error {
	targetName, err := command.GetParameter("target_name")
	if err != nil {
		return err
	}
	return client.client.PerformAddTarget(targetName)
}

func (client Client) PerformDeleteTarget(command *cli.Command) error {
	targetName, err := command.GetParameter("target_name")
	if err != nil {
		return err
	}
	return client.client.PerformDeleteTarget(targetName)
}

func (client Client) PerformClearTarget(command *cli.Command) error {
	targetName, err := command.GetParameter("target_name")
	if err != nil {
		return err
	}
	response, err := client.client.PerformClearTarget(targetName)
	if err != nil {
		return err
	}
	fmt.Println(response.ToCmdlineOutput())
	return nil
}

func (client Client) PerformList() error {
	response, err := client.client.PerformList()
	if err != nil {
		return err
	}
	fmt.Println(response.ToCmdlineOutput())
	return nil
}

func (client Client) PerformCommand() error {
	commandName, command := client.commands.GetCurrentCommand()
	if command == nil {
		return fmt.Errorf(
			"command is nil, probably an" +
				" implementation issue of command line arguments parsing",
		)
	}
	switch commandName {
	case CommandAttach:
		return client.PerformAttach(command)
	case CommandDetachLun:
		return client.PerformDetachLun(command)
	case CommandAddTarget:
		return client.PerformAddTarget(command)
	case CommandDeleteTarget:
		return client.PerformDeleteTarget(command)
	case CommandClearTarget:
		return client.PerformClearTarget(command)
	case CommandListTargets:
		return client.PerformList()
	case "":
		return fmt.Errorf("received empty command type name")
	default:
		return fmt.Errorf("unknown command name %s", commandName)
	}
}

func main() {
	client := NewClient()
	err := client.commands.Parse(os.Args)
	if err != nil {
		if helpCmd, ok := err.(*cli.ErrHelpPageRequested); ok {
			fmt.Println(helpCmd)
			os.Exit(0)
		}
		_, err := fmt.Fprintf(os.Stderr, "%s\n", err)
		if err != nil {
			panic(err)
		}
		os.Exit(1)
	}
	err = client.PerformCommand()
	if err != nil {
		_, err := fmt.Fprintln(os.Stderr, err)
		if err != nil {
			panic(err)
		}
		os.Exit(1)
	}
}
