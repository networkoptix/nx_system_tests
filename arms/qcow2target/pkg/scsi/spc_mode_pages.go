// Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
package scsi

import "fmt"

type ModePage struct {
	// Page code
	PageCode uint8
	// Sub page code
	SubPageCode uint8
	// Rest of mode page info
	Data []byte
}

func (modePage ModePage) size() byte {
	return byte(len(modePage.Data))
}

func (modePage ModePage) toByte(pageControl byte) []byte {
	subPageFormatBitMask := byte(0x40) // this bit set in the first byte
	// of page byte representation
	// indicates whether page has subpages or not.
	var data []byte
	if modePage.SubPageCode == 0 {
		data = []byte{
			modePage.PageCode,
			modePage.size(),
		}
	} else {
		data = []byte{
			modePage.PageCode | subPageFormatBitMask,
			modePage.SubPageCode,
			// 2 bytes for size
			0x00, modePage.size(),
		}
	}
	// pageControl = 0b0 requires current values
	// pageControl = 0b1 requires changeable values
	// pageControl = 0b10 requires default values
	// pageControl = 0b11 requires saved values
	// we do not support any changeable values,
	// hence we consider current values as default and saved.
	// So we just we just check for changeable.
	if pageControl != 1 {
		data = append(data, modePage.Data...)
	}
	return data
}

type ModePages []ModePage

func (modePages ModePages) findPage(pageCode, subPageCode uint8) *ModePage {
	for _, modePage := range modePages {
		if modePage.PageCode == pageCode && modePage.SubPageCode == subPageCode {
			return &modePage
		}
	}
	return nil
}

func (modePages ModePages) toBytes(pageCode, subPageCode, pageControl uint8) ([]byte, error) {
	allModePages := byte(0x3f)
	data := make([]byte, 0, len(modePages)*30)
	if pageCode == allModePages {
		// For allModePages page code
		// return all pages for device
		if subPageCode == 0x00 {
			for _, modePage := range modePages {
				data = append(data, modePage.toByte(pageControl)...)
			}
		} else if subPageCode == 0xff {
			for _, modePage := range modePages {
				if modePage.SubPageCode == 0x00 {
					data = append(data, modePage.toByte(pageControl)...)
				}
			}
		} else {
			return nil, fmt.Errorf(
				"mode page for all pages (pageCode=%d) does not "+
					"support subpage code subPageCode=%d",
				pageCode,
				subPageCode,
			)
		}
	} else {

		selectedModePage := modePages.findPage(pageCode, subPageCode)
		if selectedModePage == nil {
			return nil, fmt.Errorf(
				"mode page pageCode=%d, subPageCode=%d not found",
				pageCode,
				subPageCode,
			)
		}
		data = append(data, selectedModePage.toByte(pageControl)...)
	}
	return data, nil
}
