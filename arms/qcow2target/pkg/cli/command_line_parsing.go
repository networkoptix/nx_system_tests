// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package cli

import (
	"fmt"
	"strings"
)

type ErrHelpPageRequested struct {
	helpMessage string
}

func (err ErrHelpPageRequested) Error() string {
	return err.helpMessage
}

type ErrCommandNotFound struct {
	commandName string
}

func (err ErrCommandNotFound) Error() string {
	return fmt.Sprintf("unknown command '%s'", err.commandName)
}

type ErrInvalidOption struct {
	option string
}

func (err ErrInvalidOption) Error() string {
	return fmt.Sprintf("invalid option -- '%s'", err.option)
}

type parameter struct {
	target           string
	shortFlag        string
	name             string
	description      string
	shortDescription string
	required         bool
	set              bool
}

func (param parameter) getFullCmdlineArgument() string {
	return "--" + param.name
}

func (param parameter) found(argument string) bool {
	return strings.HasPrefix(
		argument, param.getFullCmdlineArgument(),
	) || strings.HasPrefix(argument, param.shortFlag)
}

func (param parameter) valueInNextCmd(argument string) bool {
	return argument == param.getFullCmdlineArgument() || argument == param.shortFlag
}

func (param parameter) help() string {
	return fmt.Sprintf(
		"    %s/--%s - %s",
		param.shortFlag,
		param.name,
		param.description,
	)
}

func (param parameter) usage() string {
	return fmt.Sprintf(
		"[%s|--%s %s]",
		param.shortFlag,
		param.name,
		param.shortDescription,
	)
}

func (param *parameter) extract(value string) {
	param.target = value
	param.set = true
}

type Command struct {
	name        string
	parameters  map[string]*parameter
	description string
}

func newCommand(name, description string) *Command {
	return &Command{
		name:        name,
		parameters:  make(map[string]*parameter),
		description: description,
	}
}

func (command *Command) findParameter(commandLineArgument string) *parameter {
	for _, argument := range command.parameters {
		if argument.set {
			continue
		}
		if argument.found(commandLineArgument) {
			return argument
		}
	}
	return nil
}

func (command Command) usage() string {
	eachCommandUsages := make([]string, 0, len(command.parameters))
	for _, arg := range command.parameters {
		eachCommandUsages = append(eachCommandUsages, arg.usage())
	}
	if len(eachCommandUsages) > 0 {
		return fmt.Sprintf(
			"%s %s",
			command.name,
			strings.Join(eachCommandUsages, " "),
		)
	}
	return command.name
}

func (command Command) Help() string {
	eachCommandsDescriptions := make([]string, 0, len(command.parameters))
	for _, arg := range command.parameters {
		eachCommandsDescriptions = append(eachCommandsDescriptions, arg.help())
	}
	if len(eachCommandsDescriptions) > 0 {
		return fmt.Sprintf(
			"%s\n  Options:\n%s",
			command.description,
			strings.Join(eachCommandsDescriptions, "\n"),
		)
	} else {
		return command.description + "\n"
	}
}

func (command *Command) ParseArgs(args []string) error {
	var currentArgument *parameter
	for index, commandLineArgument := range args {
		if index == 0 {
			if commandLineArgument == "--help" || commandLineArgument == "-h" {
				return &ErrHelpPageRequested{helpMessage: command.Help()}
			}
		}
		// if previous cmdline argument was equal to
		// parameter name, then the following command
		// line argument must be parameter value,
		// for instance "--size 10" - 2 command line arguments,
		// first is name, second is value
		if currentArgument != nil {
			currentArgument.extract(commandLineArgument)
			currentArgument = nil
			continue
		}
		parameter := command.findParameter(commandLineArgument)
		if parameter != nil {
			if parameter.valueInNextCmd(commandLineArgument) {
				currentArgument = parameter
				continue
			} else {
				// if command line argument is not equal to parameter name,
				// this means that it is a situation where parameter name and
				// command line argument are separated with delimiter "="
				// e.g. --size=10
				parameterNameValuePair := strings.Split(commandLineArgument, "=")
				if len(parameterNameValuePair) != 2 {
					continue
				}
				parameter.extract(parameterNameValuePair[1])
			}
		} else {
			return &ErrInvalidOption{option: commandLineArgument}
		}
	}
	missingParametersErrorString := ""
	for _, parameter := range command.parameters {
		if !parameter.set && parameter.required {
			missingParametersErrorString += "Missing parameter:\n" + parameter.help() + "\n"
		}
	}
	if missingParametersErrorString != "" {
		return fmt.Errorf(missingParametersErrorString)
	}
	return nil
}

func (command *Command) AddParameter(
	short string,
	name string,
	description string,
	shortDescription string,
	required bool,
) *Command {
	command.parameters[name] = &parameter{
		shortFlag:        short,
		name:             name,
		description:      description,
		required:         required,
		shortDescription: shortDescription,
	}
	return command
}

func (command Command) GetParameter(parameterName string) (string, error) {
	value, ok := command.parameters[parameterName]
	if !ok {
		return "", fmt.Errorf("missing parameter %s", parameterName)
	}
	if !value.set {
		return "", fmt.Errorf("missing parameter %s", parameterName)
	}
	return value.target, nil
}

type CommandList struct {
	name        string
	description string
	commands    map[string]*Command
	// this field is set after parsing
	// command line arguments
	currentCommandName string
}

func (cmdList CommandList) usages() string {
	commandUsages := make([]string, 0, len(cmdList.commands))
	for _, cmd := range cmdList.commands {
		commandUsages = append(commandUsages, fmt.Sprintf("%s %s", cmdList.name, cmd.usage()))
	}
	return strings.Join(commandUsages, "\n") + "\n"
}

func (cmdList CommandList) Help() string {
	commandDescriptions := make([]string, 0, len(cmdList.commands))
	for name, cmd := range cmdList.commands {
		commandDescriptions = append(commandDescriptions, fmt.Sprintf("* '%s': %s", name, cmd.Help()))
	}
	return fmt.Sprintf(
		"%s - %s",
		cmdList.name,
		cmdList.description,
	) +
		"\nUsage:\n" +
		cmdList.usages() +
		"\nSupported commands:\n" +
		strings.Join(commandDescriptions, "\n\n")
}

func (cmdList *CommandList) AddCommand(name, description string) *Command {
	command := newCommand(name, description)
	cmdList.commands[name] = command
	return command
}

func (cmdList CommandList) GetCommand(name string) (*Command, bool) {
	value, ok := cmdList.commands[name]
	return value, ok
}

func (cmdList *CommandList) Parse(args []string) error {
	if len(args) < 2 {
		return fmt.Errorf("wrong command list received")
	}
	commandName := args[1]
	commandArgs := args[2:]
	command, ok := cmdList.GetCommand(commandName)
	if !ok {
		if commandName == "--help" || commandName == "help" || commandName == "-h" {
			return &ErrHelpPageRequested{helpMessage: cmdList.Help()}
		}
		return &ErrCommandNotFound{commandName: commandName}
	}
	err := command.ParseArgs(commandArgs)
	if err != nil {
		return err
	}
	cmdList.currentCommandName = commandName
	return nil
}

func (cmdList CommandList) GetCurrentCommand() (commandName string, command *Command) {
	if cmdList.currentCommandName == "" {
		return "", nil
	}
	cmd, ok := cmdList.GetCommand(cmdList.currentCommandName)
	if !ok {
		return "", nil
	}
	commandName = cmdList.currentCommandName
	command = cmd
	return
}

func NewCommandList(name, description string) *CommandList {
	return &CommandList{
		name:        name,
		description: description,
		commands:    make(map[string]*Command),
	}
}
