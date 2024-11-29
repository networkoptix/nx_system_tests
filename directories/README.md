---
Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
---
# Managing local directories and files

## Temporary directories

Create temporary directories for files produced by scripts, e.g. tests.

Directory names guarantee uniqueness and help with debugging. Names are
formatted so that sorting by name is same as by time. The names include:

- process start time (as defined in standard tools like `ps` on Linux),
- process id (PID).

## Prerequisite download

When downloading a file, it's downloaded into a local directory, which
needs to be taken care of. That's why it's here.

Define the location of download cache.

## Cleanup of temporary directories and download cache

Parallel-safe.

Rate-limited.

Zero configuration: just call it, and it'll do all the job if needed.

## Run metadata

Process start time mimics Windows tools and `ps` on Linux.

Not directly related to local files but getting process creation time,
which is the most "heavy" piece of metadata-related code, is mainly used
in directory names.

## File locks

Cross-platform.

No dependencies.

Direct interaction with the Linux and Windows API.
