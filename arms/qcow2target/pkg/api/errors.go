// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package api

type ErrIOFailure struct{} // `IO failure`

func (err ErrIOFailure) Error() string {
	return "IO failure"
}

type ErrInconsistentRequestParameters struct{}

func (err ErrInconsistentRequestParameters) Error() string {
	return "inconsistent request parameters"
}
