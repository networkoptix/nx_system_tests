# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import argparse

parser = argparse.ArgumentParser()
parser.add_argument(
    '--one',
    help="Line 1. "
         f"Line {2}. "
         "Line3.")
parser.add_argument(
    '--two',
    help=(
        "Line 1."
        f"Line {2}"
        "Line 3."))
