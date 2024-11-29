# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from browser.color import RGBColor

# See: https://networkoptix.atlassian.net/wiki/spaces/FS/pages/3358097475/Additional+Attention+Contrast#Attention-Color

# It is agreed with the design team that all color check should be lazy and only check if
# the color being checked is close to any pure color.
ERROR_RED = RGBColor(255, 0, 0)
