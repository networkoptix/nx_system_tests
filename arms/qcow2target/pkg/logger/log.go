// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package logger

import (
	"fmt"
	"log"
	"os"
	"qcow2target/pkg/common"
	"sync"
)

type LogLevel int

const (
	Error = LogLevel(iota)
	Warning
	Info
	Debug
)

var logFileLock = &sync.Mutex{}

type LoggingConfig struct {
	level LogLevel
}

type Logger struct {
	level   LogLevel
	info    *log.Logger
	warning *log.Logger
	debug   *log.Logger
	error   *log.Logger
}

var logFileInstance *LoggingConfig

func GetLoggingConfig() *LoggingConfig {
	if logFileInstance == nil {
		logFileLock.Lock()
		defer logFileLock.Unlock()
		if logFileInstance == nil {
			logFileInstance = &LoggingConfig{
				level: Info,
			}
		}
	}
	return logFileInstance
}

func SetLoggingConfig(level LogLevel) {
	loggingConfig := GetLoggingConfig()
	loggingConfig.level = level
}

func GetLogger() *Logger {
	loggingConfig := GetLoggingConfig()
	name := common.GetTraceInfo()
	return &Logger{
		level:   loggingConfig.level,
		info:    log.New(os.Stderr, fmt.Sprintf("INFO: %s ", name), log.Ldate|log.Ltime),
		warning: log.New(os.Stderr, fmt.Sprintf("WARNING: %s ", name), log.Ldate|log.Ltime),
		debug:   log.New(os.Stderr, fmt.Sprintf("DEBUG: %s ", name), log.Ldate|log.Ltime),
		error:   log.New(os.Stderr, fmt.Sprintf("ERROR: %s ", name), log.Ldate|log.Ltime),
	}
}

func (logger Logger) Error(data ...any) {
	if logger.level >= Error {
		logger.error.Println(data...)
	}
}

func (logger Logger) Warn(data ...any) {
	if logger.level >= Warning {
		logger.warning.Println(data...)
	}
}

func (logger Logger) Warning(data ...any) {
	logger.Warn(data)
}

func (logger Logger) Info(data ...any) {
	if logger.level >= Info {
		logger.info.Println(data...)
	}
}

func (logger Logger) Debug(data ...any) {
	if logger.level >= Debug {
		logger.debug.Println(data...)
	}
}

func (logger Logger) Errorf(format string, a ...any) {
	data := fmt.Sprintf(format, a...)
	logger.Error(data)
}

func (logger Logger) Warnf(format string, a ...any) {
	data := fmt.Sprintf(format, a...)
	logger.Warn(data)
}

func (logger Logger) Warningf(format string, a ...any) {
	logger.Warnf(format, a...)
}

func (logger Logger) Infof(format string, a ...any) {
	data := fmt.Sprintf(format, a...)
	logger.Info(data)
}

func (logger Logger) Debugf(format string, a ...any) {
	data := fmt.Sprintf(format, a...)
	logger.Debug(data)
}
