// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package common

import (
	"fmt"
	"runtime"
)

type ReRaisableError struct {
	message      string
	currentError error
	base         error
}

func (err *ReRaisableError) Error() string {
	current := error(err)
	if reRaisable, ok := current.(*ReRaisableError); ok {
		return reRaisable.base.Error() + "\n" + reRaisable.message
	} else {
		return current.Error()
	}
}

type LineNumberedError interface {
	Error() string
	TraceInfo() string
}

func RaiseFrom(base error, current error) *ReRaisableError {
	var message string
	if lineNumberedError, ok := current.(LineNumberedError); ok {
		message = lineNumberedError.Error() + lineNumberedError.TraceInfo()
	} else {
		message = current.Error() + GetTraceInfo()
	}
	return &ReRaisableError{
		base:         base,
		message:      message,
		currentError: current,
	}
}

func GetTraceInfo() string {
	pc, fileName, fileLine, ok := runtime.Caller(2)
	details := runtime.FuncForPC(pc)
	if ok && details != nil {
		return fmt.Sprintf("func %s() at %s:%d", details.Name(), fileName, fileLine)
	}
	return ""
}
