// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package iscsi_target

type taskQueue []*iscsiTask

func (tq taskQueue) Len() int { return len(tq) }

func (tq taskQueue) Less(i, j int) bool {
	// We want Pop to give us the highest, not lowest, priority so we use greater than here.
	return tq[i].iscsiCommand.CmdSN > tq[j].iscsiCommand.CmdSN
}

func (tq taskQueue) Swap(i, j int) {
	tq[i], tq[j] = tq[j], tq[i]
}

func (tq *taskQueue) Push(x *iscsiTask) {
	item := x
	*tq = append(*tq, item)
}

func (tq *taskQueue) Pop() *iscsiTask {
	old := *tq
	n := len(old)
	item := old[n-1]
	*tq = old[0 : n-1]
	return item
}

func (tq taskQueue) GetByTag(tag uint32) *iscsiTask {
	for _, t := range tq {
		if t.tag == tag {
			return t
		}
	}
	return nil
}

func (tq *taskQueue) RemoveByTag(tag uint32) *iscsiTask {
	old := *tq
	for i, t := range old {
		if t.tag == tag {
			*tq = append(old[:i], old[i+1:]...)
			return t
		}
	}
	return nil
}
