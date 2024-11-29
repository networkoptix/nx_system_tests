---
Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
---
## Project scripts description

`qcow2target` is a complicated software requiring multiple tests. For iscsi protocol
 testing we use `libsicsi-test-cu` which is packaged in ubuntu (there is no point 
in building the package from git). To isolate test cases and make them reproducible,
tests are being ran in `Docker`.

### Build
For building and testing, the `Makefile` is used.
So, to correctly build package locally you are gonna need:
* `make`
* `go` >= 1.18

Resulting binary names and build directory are parametrised, and you can set the following
 environment variables:
* `BIN_DIR` - directory for resulting binary and admin binary
* `BINARY_NAME` - name of the resulting binary
* `ADMIN_BINARY_NAME` - name of the admin binary (used to communicate with the demon via unix socket)
* `TMP` - directory for unit tests, not used in build target. It stores test build results
 and other information.

#### Public targets:
* `all` - all is invoked by simple calling `make` in the project root, 
it fetches dependencies, builds `qcow2target` binary in created `BIN_DIR` and 
`BINARY_NAME` and also builds admin utility with `ADMIN_BINARY_NAME`.
* `clean` - removes `BIN_DIR` and all of its contents.
* `test` - executes unit tests for `qcow2` format (some other unit tests would 
be available in the future). All test data is available in `TMP` directory.

Other build targets are considered private, but you can use `build` and `admin_build`,
to rebuild admin utility and `qcow2target` demon separately, but there is no guarantee
of directories and dependencies present.

Unit tests require `qemu-img` utility installed, to create qcow2 disks for tests.

### Package build
Packages creation scripts are located inside `packaging` directory.
As for now, only debian packaging is supported. All `dpkg` specific scripts
are stored in `packaging/ubuntu` directory, almost all scripts and `control` file
inside `packaging/ubuntu/debian` are `envsubst` templated, which are substituted by
`packagin/ubuntu/build_debian_package.sh`. 

`build_debian_package.sh` is invoked with a directory to place resulting 
package after build as a first command line parameter.
The script requires `gettext-base` package (`envsubst` binary), which is usually present
on almost all popular repos, and `dpkg` to build debian package.

The `debian` directory contents equals `DEBIAN` directory
contents in the directory of the final package.

The `packaging/target.service` is also a `envsubst` template, but it can be used
in any systemd-based linux distributions, so it is located outside the `ubuntu` directory.

Using `build_debian_package.sh` directly is discouraged, since it creates
 package directory and build directory at the project root, and does not care about
 cleanup and also it requires dependencies which are not present in non-debian distributions.

#### Build in docker:

Package build in `docker` is described in `docker/debian_builder/Dockerfile`,
which invokes `build_debian_package.sh` inside the container.
Building, running the container and retrieving the resulting package is preformed
 via `build_deb_in_docker.sh` script which does not require any arguments and dependencies
 except for `docker` and puts the resulting package into project root.

### Integration testing

As for now, all integration tests are executed via iscsi-test-cu.
https://github.com/sahlberg/libiscsi 
For local run, on Linux distributions other than `ubuntu`, 
`libiscsi` shall be installed from sources. Before building `libsics`, `libcunit`
installation is required. On `ubuntu`, `libiscsi-bin` package is required.
For local unit-test run, use `run_iscsi_tests_native.sh`, logs and iscsi disks would be
 found in `build` directory. 

To run integration tests in `docker`, resulting logs can be found in `/tmp/tgt.log`.

#### Excluding tests

List of tests cases for `iscsi-test-cu` can be found in `test/libsicsi-test.sh`,
in `TESTCASES` array variable. You can change it's contents for your liking.